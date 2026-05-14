"""토스페이먼츠 테스트 결제 — 준비(주문 생성)·승인·웹훅."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.toss_payments import confirm_payment, get_payment, verify_toss_webhook_signature
from app.database import get_db
from app.models import DiagnosisResult, Opinion, PaymentOrder, Pet, User, Vet
from app.routers.dependencies import get_current_user
from app.schemas import OpinionRequestCreate

router = APIRouter(prefix="/payments", tags=["payments"])


class TossConfirmBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    payment_key: str = Field(alias="paymentKey")
    order_id: str = Field(alias="orderId")
    amount: int = Field(gt=0)


def _diagnosis_for_owner(db: Session, user_id: int, diagnosis_id: int) -> DiagnosisResult | None:
    return (
        db.query(DiagnosisResult)
        .join(Pet, Pet.id == DiagnosisResult.pet_id)
        .filter(DiagnosisResult.id == diagnosis_id, Pet.owner_id == user_id)
        .first()
    )


def _finalize_order_paid(db: Session, order: PaymentOrder, payment_key: str) -> Opinion:
    if order.opinion_id:
        existing = db.query(Opinion).filter(Opinion.id == order.opinion_id).first()
        if existing:
            order.payment_key = payment_key
            order.status = "paid"
            order.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

    opinion = Opinion(
        diagnosis_id=order.diagnosis_id,
        vet_id=order.vet_id,
        symptom_memo=order.symptom_memo,
        service_fee=order.amount,
    )
    db.add(opinion)
    db.flush()
    order.opinion_id = opinion.id
    order.payment_key = payment_key
    order.status = "paid"
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(opinion)
    return opinion


@router.post("/toss/prepare")
def toss_prepare(
    payload: OpinionRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """소견 요청과 동일한 검증 후 결제 주문(pending) 생성. 프론트는 반환값으로 토스 SDK 결제창을 연다."""
    if not settings.toss_payments_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="토스페이먼츠 키가 설정되지 않았습니다. backend/.env 에 테스트 키를 넣으세요.",
        )

    diagnosis = _diagnosis_for_owner(db, current_user.id, payload.diagnosis_id)
    if not diagnosis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="진단 결과를 찾을 수 없습니다.")

    vet = db.query(Vet).filter(Vet.id == payload.vet_id).first()
    if not vet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="수의사를 찾을 수 없습니다.")

    amount = settings.OPINION_SERVICE_FEE_WON
    toss_order_id = f"op{secrets.token_hex(10)}"

    row = PaymentOrder(
        user_id=current_user.id,
        toss_order_id=toss_order_id,
        amount=amount,
        currency="KRW",
        status="pending",
        vet_id=payload.vet_id,
        diagnosis_id=payload.diagnosis_id,
        symptom_memo=payload.symptom_memo,
    )
    db.add(row)
    db.commit()

    origin = settings.FRONTEND_ORIGIN.rstrip("/")
    customer_key = f"ck_{secrets.token_hex(16)}"
    return {
        "clientKey": settings.TOSS_PAYMENTS_CLIENT_KEY,
        "customerKey": customer_key,
        "orderId": toss_order_id,
        "amount": amount,
        "orderName": "수의사 원격 소견",
        "successUrl": f"{origin}/payment/toss/success",
        "failUrl": f"{origin}/payment/toss/fail",
    }


@router.post("/toss/confirm")
def toss_confirm(
    body: TossConfirmBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """결제창 성공 리다이렉트 후 호출. 서버에서 토스 승인 API를 호출하고 Opinion 을 생성한다."""
    if not settings.toss_payments_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="토스페이먼츠 키가 설정되지 않았습니다.",
        )

    order = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.toss_order_id == body.order_id,
            PaymentOrder.user_id == current_user.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="주문을 찾을 수 없습니다.")
    if order.amount != body.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="결제 금액이 주문과 일치하지 않습니다.")

    if order.status == "paid" and order.opinion_id:
        return {"status": "paid", "opinionId": order.opinion_id, "duplicate": True}

    ok, _code, resp = confirm_payment(
        settings.TOSS_PAYMENTS_SECRET_KEY,
        body.payment_key,
        body.order_id,
        body.amount,
    )
    if ok:
        opinion = _finalize_order_paid(db, order, body.payment_key)
        return {"status": "paid", "opinionId": opinion.id, "duplicate": False}

    ok_g, _, pay_body = get_payment(settings.TOSS_PAYMENTS_SECRET_KEY, body.payment_key)
    ta = pay_body.get("totalAmount")
    amount_ok = int(ta) == body.amount if ta is not None else True
    if (
        ok_g
        and pay_body.get("orderId") == body.order_id
        and pay_body.get("status") == "DONE"
        and amount_ok
    ):
        db.refresh(order)
        had_opinion = order.opinion_id is not None
        opinion = _finalize_order_paid(db, order, body.payment_key)
        return {"status": "paid", "opinionId": opinion.id, "duplicate": had_opinion}

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=resp.get("message") or "토스 결제 승인에 실패했습니다.",
    )


@router.post("/toss/webhook")
async def toss_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, bool]:
    """개발자센터에 등록한 URL. 로컬에서는 ngrok 등 공개 URL 필요."""
    raw = await request.body()
    hdr = request.headers

    if settings.TOSS_WEBHOOK_SECURITY_KEY:
        sig = hdr.get("tosspayments-webhook-signature")
        if sig and not verify_toss_webhook_signature(raw, hdr, settings.TOSS_WEBHOOK_SECURITY_KEY):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json")

    if payload.get("eventType") != "PAYMENT_STATUS_CHANGED":
        return {"ok": True}

    data = payload.get("data") or {}
    order_id = data.get("orderId")
    st = data.get("status")
    if order_id:
        po = db.query(PaymentOrder).filter(PaymentOrder.toss_order_id == order_id).first()
        if po:
            po.webhook_last_status = st
            po.webhook_last_payload = payload
            po.updated_at = datetime.utcnow()
            db.commit()

    return {"ok": True}
