from fastapi import FastAPI, Request, HTTPException, status, Depends
from tortoise import models
from tortoise.contrib.fastapi import register_tortoise
from models import *

# Authentication
from authentication import *
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


oauth_scheme = OAuth2PasswordBearer(tokenUrl='token')

@app.post("/token")
async def generate_token(request_form: OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(request_form.username, request_form.password)
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth_scheme)):
    try:
        payload = jwt.decode(token, config_credential["SECRET"], algorithms=['HS256'])
        user = await User.get(id = payload.get("id"))
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return await user
    

@app.post("/user/me")
async def user_login(user: UserPydanticOut = Depends(get_current_user)):
    bussiness = await Business.get(owner = user)

    return {
        "status": "ok",
        "data": {
            "username": user.username,
            "email": user.email,
            "verified": user.is_verified,
            "joined_data": user.join_date.strftime("%b %d %Y")
        }
    }


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