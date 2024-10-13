from fastapi import FastAPI, Request, HTTPException, status
from tortoise import models
from tortoise.contrib.fastapi import register_tortoise
from models import *

# Authentication
from authentication import get_hashed_password, very_token
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# singnals
from tortoise.signals import post_save
from typing import List, Optional, Type
from tortoise import BaseDBAsyncClient

from emails import *

# response classes
from fastapi.responses import HTMLResponse

# templates
from fastapi.templating import Jinja2Templates


app = FastAPI()


@post_save(User)
async def create_business(
    sender: "Type[User]",
    instance: User,
    created: bool,
    using_db: "Optional[BaseDBAsyncClient]",
    update_fields: List[str]
) -> None:
    
    if created:
        business_obj = await Business.create(
            business_name = instance.username, owner = instance
        )

        await business_pydantic.from_tortoise_orm(business_obj)
        # send the email
        await send_email([instance.email], instance)


@app.post("/registration")
async def user_registrations(user: UserPydanticIn):
    user_info = user.model_dump(exclude_unset=True)  # dict()非推奨のためmodel_dumpを使用
    user_info["password"] = get_hashed_password(user_info["password"])
    user_obj = await User.create(**user_info) # Userモデルに新しいレコードの作成
    print(user_obj)
    new_user = await user_pydantic.from_tortoise_orm(user_obj) # TortoiseORMモデルを基にPydanticモデル(user_pydantic)を作成する
    return {
        "status": "ok",
        "data": f"Hello {new_user.username}, thanks for choosing our services. Please check your email in box and click on the link to confirm your registration."
    }

templates = Jinja2Templates(directory="templates")

@app.get("/verification", response_class=HTMLResponse)
async def email_verification(request: Request, token: str):
    user = await very_token(token)

    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        return templates.TemplateResponse("verification.html", {"request": request, "username": user.username})
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token or expired token",
        headers={"wWWW-Authenticate": "Bearer"}
    )

@app.get("/")
def index():
    return {"Message": "Hello world"}

register_tortoise(
    app,
    db_url="sqlite://database.sqlite3",
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True
)