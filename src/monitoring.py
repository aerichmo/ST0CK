import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import json
import requests

logger = logging.getLogger(__name__)

class TradingMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.alerts_enabled = config.get('alerts_enabled', True)
        self.email_config = config.get('email', {})
        self.webhook_url = config.get('webhook_url')
        
    def send_alert(self, subject: str, message: str, priority: str = 'normal'):
        """Send alert via configured channels"""
        if not self.alerts_enabled:
            return
        
        logger.info(f"Alert [{priority}]: {subject}")
        
        if self.email_config.get('enabled'):
            self._send_email_alert(subject, message, priority)
        
        if self.webhook_url:
            self._send_webhook_alert(subject, message, priority)
    
    def _send_email_alert(self, subject: str, message: str, priority: str):
        """Send email alert"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from']
            msg['To'] = self.email_config['to']
            msg['Subject'] = f"[Trading Alert - {priority.upper()}] {subject}"
            
            body = f"""
Trading Alert
=============

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Priority: {priority.upper()}

{message}

---
Automated Trading System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.email_config['smtp_server'], 
                                 self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], 
                        self.email_config['password'])
            
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def _send_webhook_alert(self, subject: str, message: str, priority: str):
        """Send webhook alert (e.g., to Slack or Discord)"""
        try:
            payload = {
                'text': f"*{subject}*\n{message}",
                'priority': priority,
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def monitor_risk_breach(self, risk_metrics: Dict):
        """Monitor for risk limit breaches"""
        risk_threshold = self.config.get('monitoring', {}).get('risk_threshold_pct', -2.5)
        if risk_metrics['daily_pnl_pct'] <= risk_threshold:
            self.send_alert(
                "Risk Warning: Approaching Daily Loss Limit",
                f"Daily P&L: {risk_metrics['daily_pnl_pct']:.2f}%\n"
                f"Current Equity: ${risk_metrics['current_equity']:,.2f}",
                priority='high'
            )
        
        if not risk_metrics['trading_enabled']:
            self.send_alert(
                "Trading Disabled by Risk Guard",
                f"Reason: Daily loss limit or consecutive losses exceeded\n"
                f"Daily P&L: ${risk_metrics['daily_pnl']:,.2f}\n"
                f"Consecutive Losses: {risk_metrics['consecutive_losses']}",
                priority='critical'
            )
    
    def monitor_position_alerts(self, positions: List[Dict]):
        """Monitor positions for alert conditions"""
        for position in positions:
            loss_threshold = self.config.get('monitoring', {}).get('loss_threshold_dollars', -500)
            if position.get('unrealized_pnl', 0) < loss_threshold:
                self.send_alert(
                    f"Large Unrealized Loss: {position['symbol']}",
                    f"Position: {position['position_id']}\n"
                    f"Unrealized P&L: ${position['unrealized_pnl']:,.2f}\n"
                    f"Entry Price: ${position['entry_price']:.2f}",
                    priority='high'
                )
    
    def send_daily_summary(self, daily_stats: Dict):
        """Send daily trading summary"""
        message = f"""
Daily Trading Summary
====================

Date: {datetime.now().strftime('%Y-%m-%d')}

Performance Metrics:
- Total Trades: {daily_stats['total_trades']}
- Winners: {daily_stats['winners']}
- Losers: {daily_stats['losers']}
- Win Rate: {daily_stats['win_rate']:.1f}%

P&L Summary:
- Daily P&L: ${daily_stats['daily_pnl']:,.2f}
- Daily P&L %: {daily_stats['daily_pnl_pct']:.2f}%
- Total Realized P&L: ${daily_stats['total_realized_pnl']:,.2f}

Risk Metrics:
- Consecutive Losses: {daily_stats['consecutive_losses']}
- Max Drawdown: ${daily_stats['max_drawdown']:,.2f}

Account Status:
- Current Equity: ${daily_stats['current_equity']:,.2f}
- Active Positions: {daily_stats['active_positions']}
        """
        
        self.send_alert("Daily Trading Summary", message, priority='normal')
    
    def log_system_health(self, health_metrics: Dict):
        """Log system health metrics"""
        logger.info(f"System Health: {json.dumps(health_metrics, indent=2)}")
        
        if health_metrics.get('data_feed_status') != 'connected':
            self.send_alert(
                "Data Feed Connection Lost",
                "Unable to receive market data. Check connection.",
                priority='critical'
            )
        
        if health_metrics.get('broker_status') != 'connected':
            self.send_alert(
                "Broker Connection Lost",
                "Unable to execute trades. Check broker connection.",
                priority='critical'
            )