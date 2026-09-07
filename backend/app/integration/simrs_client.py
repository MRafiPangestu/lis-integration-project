import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.core.config import settings

class SimrsResponse(BaseModel):
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SimrsClient:
    """
    Generic HTTP client foundation for future SIMRS integration.
    This client is independent of SQLAlchemy ORM, FastAPI routers, and business logic.
    """
    
    @staticmethod
    def send(payload: Dict[str, Any]) -> SimrsResponse:
        if not settings.SIMRS_BASE_URL:
            return SimrsResponse(
                success=False,
                error="SIMRS configuration missing: SIMRS_BASE_URL is not set."
            )
            
        url = f"{settings.SIMRS_BASE_URL.rstrip('/')}/{settings.SIMRS_ENDPOINT.lstrip('/')}"
        
        headers = {"Content-Type": "application/json"}
        if settings.SIMRS_API_KEY:
            # Generic secret injection. The final SIMRS authentication contract may 
            # require a different header name (e.g. X-API-Key) or scheme (e.g. Bearer).
            headers["Authorization"] = settings.SIMRS_API_KEY
            
        try:
            with httpx.Client(timeout=settings.SIMRS_TIMEOUT) as client:
                response = client.post(url, json=payload, headers=headers)
                
            response.raise_for_status()
            
            try:
                resp_body = response.json()
            except ValueError:
                resp_body = {"raw_text": response.text}
                
            return SimrsResponse(
                success=True,
                status_code=response.status_code,
                response_body=resp_body
            )
            
        except httpx.HTTPStatusError as e:
            try:
                resp_body = e.response.json()
            except ValueError:
                resp_body = {"raw_text": e.response.text}
                
            return SimrsResponse(
                success=False,
                status_code=e.response.status_code,
                response_body=resp_body,
                error=f"HTTP Error: {e.response.status_code}"
            )
        except httpx.TimeoutException:
            return SimrsResponse(
                success=False,
                error="Connection timed out while waiting for SIMRS response."
            )
        except httpx.RequestError as e:
            return SimrsResponse(
                success=False,
                error=f"Network error during request: {str(e)}"
            )
        except Exception as e:
            return SimrsResponse(
                success=False,
                error=f"Unexpected client exception: {str(e)}"
            )

