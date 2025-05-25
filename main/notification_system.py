import json
import platform
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from .error_handling import NotificationError
from .logging_manager import Logger

class NotificationSystem:
    """Manage and send notifications"""
    
    def __init__(self, logger: Logger):
        """Initialize notification system"""
        self.logger = logger
        self.notifications: List[Dict[str, Any]] = []
        self.notification_handlers: List['NotificationHandler'] = []
        self.platform = platform.system()
        
    def register_handler(self, handler: 'NotificationHandler') -> None:
        """Register a notification handler"""
        self.notification_handlers.append(handler)
        self.logger.info(f"Registered notification handler: {handler.__class__.__name__}")
    
    def send_notification(self, title: str, message: str, level: str = 'info') -> None:
        """Send a notification"""
        try:
            # Create notification
            notification = {
                'title': title,
                'message': message,
                'level': level,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add to history
            self.notifications.append(notification)
            
            # Send to all handlers
            for handler in self.notification_handlers:
                handler.send_notification(notification)
                
            self.logger.info(f"Sent notification: {title}")
            
        except Exception as e:
            self.logger.error(f"Error sending notification: {str(e)}")
            raise NotificationError(f"Failed to send notification: {str(e)}")
    
    def get_notifications(self) -> List[Dict[str, Any]]:
        """Get notification history"""
        return self.notifications.copy()
    
    def clear_notifications(self) -> None:
        """Clear notification history"""
        self.notifications.clear()
        self.logger.info("Cleared notification history")

class NotificationHandler(ABC):
    """Base class for notification handlers"""
    
    @abstractmethod
    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send a notification"""
        pass

class ConsoleNotificationHandler(NotificationHandler):
    """Handle notifications by printing to console"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        
    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification to console"""
        try:
            level = notification['level'].upper()
            message = f"[{level}] {notification['title']}: {notification['message']}"
            
            if level == 'ERROR':
                self.logger.error(message)
            elif level == 'WARNING':
                self.logger.warning(message)
            else:
                self.logger.info(message)
                
        except Exception as e:
            self.logger.error(f"Error sending console notification: {str(e)}")
            raise NotificationError(f"Failed to send console notification: {str(e)}")

class FileNotificationHandler(NotificationHandler):
    """Handle notifications by writing to file"""
    
    def __init__(self, logger: Logger, log_file: str):
        self.logger = logger
        self.log_file = log_file
        
    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification to file"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                json.dump(notification, f)
                f.write('\n')
                
        except Exception as e:
            self.logger.error(f"Error sending file notification: {str(e)}")
            raise NotificationError(f"Failed to send file notification: {str(e)}")

class WebNotificationHandler(NotificationHandler):
    """Handle notifications by sending to web interface"""
    
    def __init__(self, logger: Logger, web_socket: Any):
        self.logger = logger
        self.web_socket = web_socket
        
    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification to web interface"""
        try:
            if self.web_socket:
                self.web_socket.send(json.dumps(notification))
                
        except Exception as e:
            self.logger.error(f"Error sending web notification: {str(e)}")
            raise NotificationError(f"Failed to send web notification: {str(e)}")
