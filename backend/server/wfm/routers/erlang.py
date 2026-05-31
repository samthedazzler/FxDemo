import math
from fastapi import APIRouter, HTTPException
from wfm.models import ErlangCRequest, ErlangCResult, ErlangBRequest, ErlangBResult

router = APIRouter()

# ── Erlang C ──────────────────────────────────────────────────────────────────

def _erlang_c_prob(N: int, A: float) -> float:
    """P(W>0) — probability a call waits (Erlang C formula)."""
    if N <= A:
        return 1.0
    # Numerator: (A^N / N!) * (N / (N - A))
    # Denominator: sum(A^k/k!, k=0..N-1) + (A^N/N!) * (N/(N-A))
    # Computed in log-space for numerical stability
    log_AN_over_Nfact = N * math.log(A) - sum(math.log(i) for i in range(1, N + 1))
    AN_over_Nfact = math.exp(log_AN_over_Nfact)
    erlang_b_inv = sum(
        math.exp(k * math.log(A) - sum(math.log(i) for i in range(1, k + 1)))
        for k in range(N)
    )
    numerator   = AN_over_Nfact * (N / (N - A))
    denominator = erlang_b_inv + numerator
    return numerator / denominator if denominator else 1.0

def _service_level(N: int, A: float, t: int, aht: int) -> float:
    """SL = 1 - P(W>0) * exp(-(N-A)*t/AHT)"""
    if N <= A:
        return 0.0
    pw  = _erlang_c_prob(N, A)
    sl  = 1 - pw * math.exp(-(N - A) * t / aht)
    return max(0.0, min(1.0, sl))

def _asa(N: int, A: float, aht: int) -> float:
    """Average Speed of Answer in seconds."""
    if N <= A:
        return float("inf")
    pw = _erlang_c_prob(N, A)
    return pw * aht / (N - A)

@router.post("/erlang-c", response_model=ErlangCResult)
def erlang_c(payload: ErlangCRequest):
    """Calculate agents required to meet a service level target."""
    calls_per_hour = payload.calls_per_interval * (60 / payload.interval_minutes)
    A = (calls_per_hour * payload.aht_seconds) / 3600  # Traffic intensity in Erlangs

    if A <= 0:
        raise HTTPException(status_code=400, detail="Traffic intensity must be > 0")

    # Find minimum N that meets SL target
    N = math.ceil(A) + 1
    for _ in range(500):
        sl = _service_level(N, A, payload.service_time_target_seconds, payload.aht_seconds)
        if sl >= payload.service_level_target:
            break
        N += 1

    pw         = _erlang_c_prob(N, A)
    occupancy  = A / N
    asa_val    = _asa(N, A, payload.aht_seconds)

    # Sensitivity table: N-3 to N+3
    sensitivity = []
    for n in range(max(math.ceil(A) + 1, N - 3), N + 4):
        sl_n  = _service_level(n, A, payload.service_time_target_seconds, payload.aht_seconds)
        occ_n = A / n
        asa_n = _asa(n, A, payload.aht_seconds)
        sensitivity.append({
            "agents": n,
            "sl_pct": round(sl_n * 100, 1),
            "occupancy_pct": round(occ_n * 100, 1),
            "asa_seconds": round(asa_n, 1),
            "recommended": n == N,
        })

    return ErlangCResult(
        agents_required=N,
        traffic_intensity_erlangs=round(A, 2),
        occupancy=round(occupancy * 100, 1),
        prob_waiting=round(pw * 100, 1),
        avg_speed_of_answer=round(asa_val, 1),
        sensitivity=sensitivity,
    )

# ── Erlang B ──────────────────────────────────────────────────────────────────

def _erlang_b(N: int, A: float) -> float:
    """Erlang B blocking probability — recursive formula."""
    B = 1.0
    for n in range(1, N + 1):
        B = (A * B) / (n + A * B)
    return B

@router.post("/erlang-b", response_model=ErlangBResult)
def erlang_b(payload: ErlangBRequest):
    """Calculate trunk lines required to meet a blocking probability target."""
    A       = payload.busy_hour_traffic_erlangs
    target  = payload.target_blocking_pct / 100

    N = math.ceil(A)
    for _ in range(500):
        if _erlang_b(N, A) <= target:
            break
        N += 1

    actual_blocking = _erlang_b(N, A)

    sensitivity = []
    for n in range(max(1, N - 5), N + 4):
        b = _erlang_b(n, A)
        sensitivity.append({
            "trunks": n,
            "blocking_pct": round(b * 100, 2),
            "utilisation_pct": round(A / n * 100, 1),
            "recommended": n == N,
        })

    return ErlangBResult(
        trunks_required=N,
        actual_blocking_pct=round(actual_blocking * 100, 2),
        traffic_per_trunk=round(A / N, 2),
        utilisation=round(A / N * 100, 1),
        sensitivity=sensitivity,
    )
