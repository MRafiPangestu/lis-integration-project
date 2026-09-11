from fastapi import APIRouter
from app.api.routers import account, instruments, patients, results, test_runs, users

# Every router mounted here is protected: app.main mounts this whole
# APIRouter under "/api" with `dependencies=[Depends(get_current_user)]`
# (deny-by-default, design §7.1). The one exception is the public login
# endpoint (app.api.routers.auth), which app.main mounts separately with no
# such dependency.
api_router = APIRouter()
api_router.include_router(test_runs.router, tags=["Test Runs"])
api_router.include_router(results.router)
api_router.include_router(patients.router)
api_router.include_router(instruments.router)
api_router.include_router(account.router)
api_router.include_router(users.router)

