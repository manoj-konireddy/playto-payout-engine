from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import OperationalError

from .models import Merchant
from .serializers import PayoutCreateSerializer, PayoutSerializer
from .services import (
    DuplicateIdempotencyInFlight,
    IdempotencyConflict,
    create_payout_with_idempotency,
    get_dashboard_data,
)


def _merchant_from_header(request):
    merchant_id = request.headers.get('X-Merchant-Id')
    if not merchant_id:
        return None
    try:
        merchant_id = int(merchant_id)
    except ValueError:
        return None
    return Merchant.objects.filter(id=merchant_id).first()


class MerchantDashboardView(APIView):
    def get(self, request):
        merchant = _merchant_from_header(request)
        if not merchant:
            return Response({'error': 'Valid X-Merchant-Id header is required'}, status=400)
        return Response(get_dashboard_data(merchant), status=200)


class PayoutListCreateView(APIView):
    def get(self, request):
        merchant = _merchant_from_header(request)
        if not merchant:
            return Response({'error': 'Valid X-Merchant-Id header is required'}, status=400)
        payouts = merchant.payouts.all()[:20]
        return Response(PayoutSerializer(payouts, many=True).data, status=200)

    def post(self, request):
        merchant = _merchant_from_header(request)
        if not merchant:
            return Response({'error': 'Valid X-Merchant-Id header is required'}, status=400)
        idem_key = request.headers.get('Idempotency-Key')
        if not idem_key:
            return Response({'error': 'Idempotency-Key header is required'}, status=400)

        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            status_code, body = create_payout_with_idempotency(
                merchant_id=merchant.id,
                idempotency_key=idem_key,
                payload=serializer.validated_data,
            )
            return Response(body, status=status_code)
        except DuplicateIdempotencyInFlight as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
        except IdempotencyConflict as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
        except OperationalError:
            return Response({'error': 'Database lock contention, retry request'}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
