#!/usr/bin/env python3
"""
Log Analyzer - Parse and analyze Railway logs for patterns and issues

Usage:
    # Analyze recent logs
    railway logs --tail 500 | python log_analyzer.py

    # Find specific issues
    railway logs --tail 1000 | python log_analyzer.py --find-errors

    # Track a specific call
    railway logs --tail 500 | python log_analyzer.py --call-sid CA12345

    # Performance analysis
    railway logs --tail 500 | python log_analyzer.py --performance
"""

import sys
import re
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any


class LogEntry:
    """Parsed log entry"""
    def __init__(self, raw_line: str):
        self.raw = raw_line
        self.timestamp = None
        self.level = "INFO"
        self.message = ""
        self.call_sid = None
        self.stream_sid = None
        self.phone = None
        self.parse()

    def parse(self):
        """Parse log line"""
        # Extract timestamp
        ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', self.raw)
        if ts_match:
            try:
                self.timestamp = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S,%f')
            except:
                pass

        # Extract log level
        if 'ERROR' in self.raw:
            self.level = 'ERROR'
        elif 'WARNING' in self.raw:
            self.level = 'WARNING'
        elif 'DEBUG' in self.raw:
            self.level = 'DEBUG'

        # Extract call identifiers
        call_match = re.search(r'CA[0-9a-f]{32}', self.raw)
        if call_match:
            self.call_sid = call_match.group(0)

        stream_match = re.search(r'MZ[0-9a-f]{32}', self.raw)
        if stream_match:
            self.stream_sid = stream_match.group(0)

        phone_match = re.search(r'\+\d{11}', self.raw)
        if phone_match:
            self.phone = phone_match.group(0)

        # Extract message
        msg_match = re.search(r'INFO - (.+)$', self.raw)
        if msg_match:
            self.message = msg_match.group(1)
        else:
            self.message = self.raw


class LogAnalyzer:
    """Analyzes logs for patterns and issues"""

    def __init__(self):
        self.entries: List[LogEntry] = []
        self.calls: Dict[str, List[LogEntry]] = defaultdict(list)
        self.errors: List[LogEntry] = []
        self.warnings: List[LogEntry] = []

    def add_line(self, line: str):
        """Add a log line"""
        if not line.strip():
            return

        entry = LogEntry(line)
        self.entries.append(entry)

        if entry.call_sid:
            self.calls[entry.call_sid].append(entry)

        if entry.level == 'ERROR':
            self.errors.append(entry)
        elif entry.level == 'WARNING':
            self.warnings.append(entry)

    def find_issues(self) -> Dict[str, Any]:
        """Find common issues in logs"""
        issues = {
            "race_conditions": [],
            "audio_errors": [],
            "state_errors": [],
            "websocket_issues": [],
            "timing_issues": []
        }

        for entry in self.entries:
            msg = entry.message.lower()

            # Race condition: operations after disconnect
            if 'disconnected' in msg and 'skipping' in msg:
                issues["race_conditions"].append({
                    "time": entry.timestamp,
                    "call_sid": entry.call_sid,
                    "message": entry.message
                })

            # Audio conversion errors
            if 'ffmpeg' in msg or 'audio' in msg and 'error' in msg:
                issues["audio_errors"].append({
                    "time": entry.timestamp,
                    "call_sid": entry.call_sid,
                    "message": entry.message
                })

            # State errors
            if 'invalid' in msg and 'state' in msg:
                issues["state_errors"].append({
                    "time": entry.timestamp,
                    "call_sid": entry.call_sid,
                    "message": entry.message
                })

            # WebSocket issues
            if 'websocket' in msg and ('failed' in msg or 'error' in msg or 'closed' in msg):
                issues["websocket_issues"].append({
                    "time": entry.timestamp,
                    "call_sid": entry.call_sid,
                    "message": entry.message
                })

        return issues

    def analyze_call(self, call_sid: str) -> Dict[str, Any]:
        """Analyze a specific call"""
        if call_sid not in self.calls:
            return {"error": f"Call {call_sid} not found in logs"}

        entries = self.calls[call_sid]

        # Extract timing
        start = entries[0].timestamp if entries and entries[0].timestamp else None
        end = entries[-1].timestamp if entries and entries[-1].timestamp else None
        duration = (end - start).total_seconds() if start and end else None

        # Extract states
        states = []
        for entry in entries:
            if 'state:' in entry.message.lower() or 'greeting' in entry.message.lower() or 'listening' in entry.message.lower():
                states.append(entry.message)

        # Extract errors
        call_errors = [e for e in entries if e.level == 'ERROR']

        return {
            "call_sid": call_sid,
            "duration": f"{duration:.1f}s" if duration else "unknown",
            "num_events": len(entries),
            "states": states,
            "errors": [e.message for e in call_errors],
            "phone": entries[0].phone if entries else None
        }

    def performance_metrics(self) -> Dict[str, Any]:
        """Extract performance metrics"""
        metrics = {
            "greeting_times": [],
            "response_times": [],
            "transcription_times": [],
            "tts_times": []
        }

        # Look for timing patterns
        for entry in self.entries:
            msg = entry.message

            # Greeting timing
            if 'greeting' in msg.lower() and 'finished' in msg.lower():
                time_match = re.search(r'(\d+\.\d+)s', msg)
                if time_match:
                    metrics["greeting_times"].append(float(time_match.group(1)))

            # Response timing
            if 'gpt response' in msg.lower():
                # Look for next entry with timing
                pass  # TODO: implement

        # Calculate averages
        result = {}
        for key, values in metrics.items():
            if values:
                result[key] = {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }

        return result

    def print_report(self):
        """Print analysis report"""
        print(f"\n{'='*60}")
        print(f"LOG ANALYSIS REPORT")
        print(f"{'='*60}\n")

        print(f"Total Entries: {len(self.entries)}")
        print(f"Unique Calls: {len(self.calls)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for err in self.errors[-10:]:  # Last 10 errors
                ts = err.timestamp.strftime('%H:%M:%S') if err.timestamp else "??:??:??"
                print(f"  [{ts}] {err.message[:100]}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings[-5:]:  # Last 5 warnings
                ts = warn.timestamp.strftime('%H:%M:%S') if warn.timestamp else "??:??:??"
                print(f"  [{ts}] {warn.message[:100]}")

        issues = self.find_issues()
        print(f"\n🔍 ISSUES FOUND:")
        for issue_type, issue_list in issues.items():
            if issue_list:
                print(f"\n{issue_type.replace('_', ' ').title()}: {len(issue_list)}")
                for issue in issue_list[:3]:  # First 3 of each type
                    ts = issue['time'].strftime('%H:%M:%S') if issue['time'] else "??:??:??"
                    print(f"  [{ts}] {issue['message'][:80]}")

        print(f"\n{'='*60}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Analyze Railway logs')
    parser.add_argument('--find-errors', action='store_true', help='Focus on errors')
    parser.add_argument('--call-sid', help='Analyze specific call')
    parser.add_argument('--performance', action='store_true', help='Performance metrics')

    args = parser.parse_args()

    analyzer = LogAnalyzer()

    # Read from stdin
    for line in sys.stdin:
        analyzer.add_line(line)

    if args.call_sid:
        # Analyze specific call
        result = analyzer.analyze_call(args.call_sid)
        print(f"\nCALL ANALYSIS: {args.call_sid}")
        print(f"{'='*60}")
        for key, value in result.items():
            print(f"{key}: {value}")

    elif args.performance:
        # Performance metrics
        metrics = analyzer.performance_metrics()
        print(f"\nPERFORMANCE METRICS")
        print(f"{'='*60}")
        for metric, data in metrics.items():
            print(f"\n{metric}:")
            for k, v in data.items():
                print(f"  {k}: {v}")

    else:
        # General report
        analyzer.print_report()


if __name__ == '__main__':
    main()
