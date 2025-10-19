"""
Call Tracing and State Management for Debugging

Provides:
- Unique call IDs for tracing through logs
- State machine validation
- Performance metrics
- Structured logging

Usage:
    from debug_tracer import CallTracer, CallState

    tracer = CallTracer(call_sid, phone_number)
    tracer.transition(CallState.GREETING)
    tracer.log_event("greeting_start", greeting_text=message)
    tracer.measure("greeting_duration", start_time)
"""

import time
import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CallState(Enum):
    """Valid states for a call"""
    CONNECTING = "connecting"
    GREETING = "greeting"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


# Valid state transitions
VALID_TRANSITIONS = {
    CallState.CONNECTING: [CallState.GREETING, CallState.ERROR, CallState.DISCONNECTED],
    CallState.GREETING: [CallState.LISTENING, CallState.ERROR, CallState.DISCONNECTED],
    CallState.LISTENING: [CallState.PROCESSING, CallState.DISCONNECTING, CallState.ERROR],
    CallState.PROCESSING: [CallState.SPEAKING, CallState.LISTENING, CallState.ERROR, CallState.DISCONNECTED],
    CallState.SPEAKING: [CallState.LISTENING, CallState.DISCONNECTING, CallState.ERROR],
    CallState.DISCONNECTING: [CallState.DISCONNECTED],
    CallState.DISCONNECTED: [],  # Terminal state
    CallState.ERROR: [CallState.DISCONNECTED],  # Can only go to disconnected from error
}


class CallTracer:
    """Traces a single call through its lifecycle"""

    def __init__(self, call_sid: str, phone_number: str, stream_sid: Optional[str] = None):
        self.call_sid = call_sid
        self.phone_number = phone_number
        self.stream_sid = stream_sid or "unknown"
        self.state = CallState.CONNECTING
        self.start_time = time.time()
        self.state_history: list[tuple[float, CallState]] = [(self.start_time, CallState.CONNECTING)]
        self.events: list[Dict[str, Any]] = []
        self.metrics: Dict[str, float] = {}
        self.errors: list[Dict[str, Any]] = []

        self._log(f"📞 Call started - {phone_number}")

    def _log(self, message: str, level: str = "INFO", **kwargs):
        """Structured logging with call context"""
        context = {
            "call_sid": self.call_sid,
            "stream_sid": self.stream_sid,
            "phone": self.phone_number,
            "state": self.state.value,
            "duration": f"{time.time() - self.start_time:.1f}s",
            **kwargs
        }

        context_str = " ".join(f"{k}={v}" for k, v in context.items())
        full_message = f"[{self.call_sid[:8]}] {message} | {context_str}"

        if level == "ERROR":
            logger.error(full_message)
        elif level == "WARNING":
            logger.warning(full_message)
        else:
            logger.info(full_message)

    def transition(self, new_state: CallState, reason: str = "") -> bool:
        """
        Transition to new state with validation

        Returns True if transition was valid, False otherwise
        """
        if new_state not in VALID_TRANSITIONS[self.state]:
            self._log(
                f"❌ INVALID STATE TRANSITION: {self.state.value} → {new_state.value}",
                level="ERROR",
                reason=reason,
                valid_transitions=[s.value for s in VALID_TRANSITIONS[self.state]]
            )
            self.errors.append({
                "type": "invalid_transition",
                "from": self.state.value,
                "to": new_state.value,
                "reason": reason,
                "time": time.time()
            })
            return False

        old_state = self.state
        self.state = new_state
        self.state_history.append((time.time(), new_state))

        self._log(
            f"🔄 State: {old_state.value} → {new_state.value}",
            reason=reason
        )
        return True

    def log_event(self, event_name: str, **kwargs):
        """Log an event with context"""
        event = {
            "name": event_name,
            "time": time.time(),
            "state": self.state.value,
            **kwargs
        }
        self.events.append(event)
        self._log(f"📝 {event_name}", **kwargs)

    def measure(self, metric_name: str, start_time: Optional[float] = None):
        """
        Measure duration of an operation

        If start_time provided, measures from that time to now
        Otherwise, measures from call start
        """
        if start_time:
            duration = time.time() - start_time
        else:
            duration = time.time() - self.start_time

        self.metrics[metric_name] = duration
        self._log(f"⏱️ {metric_name}: {duration:.2f}s")
        return duration

    def log_error(self, error_type: str, error_msg: str, **kwargs):
        """Log an error"""
        error = {
            "type": error_type,
            "message": error_msg,
            "time": time.time(),
            "state": self.state.value,
            **kwargs
        }
        self.errors.append(error)
        self._log(f"❌ ERROR: {error_type} - {error_msg}", level="ERROR", **kwargs)

    def check_state(self, expected_state: CallState, operation: str) -> bool:
        """
        Check if we're in expected state before operation

        Returns True if in correct state, False otherwise (and logs error)
        """
        if self.state != expected_state:
            self.log_error(
                "invalid_state_for_operation",
                f"Cannot {operation} in state {self.state.value}, expected {expected_state.value}",
                operation=operation,
                expected=expected_state.value,
                actual=self.state.value
            )
            return False
        return True

    def is_disconnected(self) -> bool:
        """Check if call is disconnected"""
        return self.state == CallState.DISCONNECTED

    def summary(self) -> Dict[str, Any]:
        """Get call summary"""
        duration = time.time() - self.start_time
        return {
            "call_sid": self.call_sid,
            "phone_number": self.phone_number,
            "duration": f"{duration:.1f}s",
            "final_state": self.state.value,
            "states_visited": [s.value for _, s in self.state_history],
            "num_events": len(self.events),
            "num_errors": len(self.errors),
            "metrics": self.metrics,
            "errors": self.errors[-5:] if self.errors else []  # Last 5 errors
        }

    def print_summary(self):
        """Print formatted summary"""
        print(f"\n{'='*60}")
        print(f"CALL SUMMARY: {self.call_sid}")
        print(f"{'='*60}")
        print(f"Phone: {self.phone_number}")
        print(f"Duration: {time.time() - self.start_time:.1f}s")
        print(f"Final State: {self.state.value}")
        print(f"\nState History:")
        for t, state in self.state_history:
            print(f"  {datetime.fromtimestamp(t).strftime('%H:%M:%S.%f')[:-3]} - {state.value}")
        print(f"\nMetrics:")
        for name, value in self.metrics.items():
            print(f"  {name}: {value:.2f}s")
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for err in self.errors[-5:]:
                print(f"  [{err['type']}] {err['message']}")
        print(f"{'='*60}\n")


# Global registry of active calls
_active_calls: Dict[str, CallTracer] = {}


def get_tracer(call_sid: str) -> Optional[CallTracer]:
    """Get tracer for a call"""
    return _active_calls.get(call_sid)


def create_tracer(call_sid: str, phone_number: str, stream_sid: Optional[str] = None) -> CallTracer:
    """Create and register a new call tracer"""
    tracer = CallTracer(call_sid, phone_number, stream_sid)
    _active_calls[call_sid] = tracer
    return tracer


def remove_tracer(call_sid: str):
    """Remove tracer from registry"""
    if call_sid in _active_calls:
        tracer = _active_calls[call_sid]
        tracer.print_summary()
        del _active_calls[call_sid]


def get_active_calls() -> list[str]:
    """Get list of active call SIDs"""
    return list(_active_calls.keys())
