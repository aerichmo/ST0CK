"""
Error reporting with structured logging and Sentry integration
Maintains GitHub Actions compatibility while adding better error tracking
"""
import os
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import sentry_sdk
from .unified_logging import get_logger, log_critical_error

# Failure type constants
FAILURE_TYPES = {
    'BATTLE_LINES': ['battle lines', 'battle_lines'],
    'SIGNAL_DETECTION': ['signal detection'],
    'MARKET_DATA': ['market data'],
    'DATABASE': ['database'],
    'BROKER_CONNECTION': ['broker', 'alpaca'],
}

class ErrorReporter:
    """Reports errors with structured logging and external tracking"""
    
    @staticmethod
    def report_failure(bot_id: str, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Report error using structured logging and Sentry
        Maintains GitHub Actions output format for compatibility
        
        Usage:
            try:
                # ... bot code ...
            except Exception as e:
                ErrorReporter.report_failure('st0ckg', e, {'battle_lines': battle_lines})
                raise
        """
        context = context or {}
        logger = get_logger(__name__, bot_id)
        
        # Determine failure type
        failure_type = _get_failure_type(error)
        
        # Log to structured logger
        log_critical_error(
            logger, 
            bot_id, 
            error,
            {
                'failure_type': failure_type,
                'context': context,
                'traceback': traceback.format_exc()
            }
        )
        
        # Maintain GitHub Actions output format
        _print_github_format(bot_id, error, context, failure_type)
        
        # Write to GitHub Actions summary if available
        _write_github_summary(bot_id, error, failure_type)
    
    @staticmethod
    def report_warning(bot_id: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Report non-critical warnings"""
        logger = get_logger(__name__, bot_id)
        logger.warning(
            f"[{bot_id}] {message}",
            extra={'bot_id': bot_id, 'context': context or {}}
        )
    
    @staticmethod
    def report_info(bot_id: str, message: str, context: Optional[Dict[str, Any]] = None):
        """Report informational messages"""
        logger = get_logger(__name__, bot_id)
        logger.info(
            f"[{bot_id}] {message}",
            extra={'bot_id': bot_id, 'context': context or {}}
        )

def _get_failure_type(error: Exception) -> str:
    """Determine failure type from error"""
    error_msg = str(error).lower()
    
    for failure_type, keywords in FAILURE_TYPES.items():
        if any(keyword in error_msg for keyword in keywords):
            return failure_type
    
    return "UNKNOWN"

def _print_github_format(bot_id: str, error: Exception, context: Dict[str, Any], failure_type: str):
    """Print error in GitHub Actions format for compatibility"""
    # Clear separator
    print("\n" + "🚨"*30)
    print(f"ST0CKG_FAILURE[{bot_id}]")
    print(f"TIME={datetime.now().isoformat()}")
    print(f"ERROR={type(error).__name__}: {str(error)}")
    print(f"FAILURE_TYPE={failure_type}")
    
    # Print specific failure details
    if failure_type == 'BATTLE_LINES':
        _print_battle_lines_status(context.get('battle_lines'))
    elif failure_type == 'SIGNAL_DETECTION':
        _print_signal_status(context.get('signals'))
    
    # Print additional context
    if context:
        print("CONTEXT_START")
        for key, value in context.items():
            if key not in ['battle_lines', 'signals']:
                print(f"  {key}={_format_value(value)}")
        print("CONTEXT_END")
    
    # Full traceback
    print("TRACE_START")
    print(traceback.format_exc())
    print("TRACE_END")
    print("🚨"*30 + "\n")

def _write_github_summary(bot_id: str, error: Exception, failure_type: str):
    """Write to GitHub Actions summary file"""
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if summary_file:
        try:
            with open(summary_file, 'a') as f:
                f.write(f"\n## ❌ {bot_id} Execution Failed\n")
                f.write(f"- **Time**: {datetime.now().isoformat()}\n")
                f.write(f"- **Error**: `{type(error).__name__}: {str(error)}`\n")
                f.write(f"- **Type**: {failure_type}\n")
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