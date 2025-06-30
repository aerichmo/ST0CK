"""
Simple error reporting for GitHub Actions
Outputs structured errors that can be easily copy/pasted
"""
import os
import traceback
from datetime import datetime
from typing import Dict, Any, Optional


class ErrorReporter:
    """Reports errors in a structured, parseable format"""
    
    @staticmethod
    def report_failure(bot_id: str, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Print error in a structured format that's easy to copy/paste from GitHub Actions
        
        Usage:
            try:
                # ... bot code ...
            except Exception as e:
                ErrorReporter.report_failure('st0ckg', e, {'battle_lines': battle_lines})
                raise
        """
        context = context or {}
        
        # Clear separator
        print("\n" + "🚨"*30)
        print(f"ST0CKG_FAILURE[{bot_id}]")
        print(f"TIME={datetime.now().isoformat()}")
        print(f"ERROR={type(error).__name__}: {str(error)}")
        
        # Check specific failure types
        error_msg = str(error).lower()
        if 'battle lines' in error_msg or 'battle_lines' in error_msg:
            print("FAILURE_TYPE=BATTLE_LINES")
            _print_battle_lines_status(context.get('battle_lines'))
        elif 'signal detection' in error_msg:
            print("FAILURE_TYPE=SIGNAL_DETECTION")
            _print_signal_status(context.get('signals'))
        elif 'market data' in error_msg:
            print("FAILURE_TYPE=MARKET_DATA")
        elif 'database' in error_msg:
            print("FAILURE_TYPE=DATABASE")
        elif 'broker' in error_msg or 'alpaca' in error_msg:
            print("FAILURE_TYPE=BROKER_CONNECTION")
        else:
            print("FAILURE_TYPE=UNKNOWN")
        
        # Print any additional context
        if context:
            print("CONTEXT_START")
            for key, value in context.items():
                if key not in ['battle_lines', 'signals']:  # Already handled above
                    print(f"  {key}={_format_value(value)}")
            print("CONTEXT_END")
        
        # Full traceback
        print("TRACE_START")
        print(traceback.format_exc())
        print("TRACE_END")
        print("🚨"*30 + "\n")
        
        # Also write to GitHub Actions summary if available
        summary_file = os.getenv('GITHUB_STEP_SUMMARY')
        if summary_file:
            try:
                with open(summary_file, 'a') as f:
                    f.write(f"\n## ❌ {bot_id} Execution Failed\n")
                    f.write(f"- **Time**: {datetime.now().isoformat()}\n")
                    f.write(f"- **Error**: `{type(error).__name__}: {str(error)}`\n")
                    f.write(f"- **Type**: {_get_failure_type(error)}\n")
            except:
                pass  # Don't fail error reporting


def _print_battle_lines_status(battle_lines: Optional[Dict]):
    """Print battle lines status"""
    print("BATTLE_LINES_STATUS=FAILED")
    if battle_lines:
        for key in ['pdh', 'pdl', 'overnight_high', 'overnight_low', 'premarket_high', 'premarket_low']:
            value = battle_lines.get(key, 'MISSING')
            print(f"  {key}={value}")
    else:
        print("  status=NOT_CALCULATED")


def _print_signal_status(signals: Optional[Dict]):
    """Print signal detection status"""
    print("SIGNALS_STATUS=FAILED")
    if signals:
        for signal_type, signal_data in signals.items():
            score = signal_data.get('score', 0) if isinstance(signal_data, dict) else 0
            print(f"  {signal_type}={score}")
    else:
        print("  status=NO_SIGNALS")


def _format_value(value: Any) -> str:
    """Format value for printing"""
    if isinstance(value, dict):
        return f"dict({len(value)} items)"
    elif isinstance(value, list):
        return f"list({len(value)} items)"
    elif isinstance(value, str) and len(value) > 50:
        return value[:50] + "..."
    else:
        return str(value)


def _get_failure_type(error: Exception) -> str:
    """Determine failure type from error"""
    error_msg = str(error).lower()
    if 'battle lines' in error_msg or 'battle_lines' in error_msg:
        return "BATTLE_LINES"
    elif 'signal detection' in error_msg:
        return "SIGNAL_DETECTION"
    elif 'market data' in error_msg:
        return "MARKET_DATA"
    elif 'database' in error_msg:
        return "DATABASE"
    elif 'broker' in error_msg or 'alpaca' in error_msg:
        return "BROKER_CONNECTION"
    else:
        return "UNKNOWN"