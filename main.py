from fastapi import Depends, FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from tortoise import models
from tortoise.contrib.fastapi import register_tortoise
from models import *
#authentication
from authentication import *
from fastapi.security import (OAuth2PasswordBearer, OAuth2PasswordRequestForm)
#signal
from tortoise.signals import post_save
from typing import List, Optional, Type
from tortoise import BaseDBAsyncClient
from email_utils import send_email
#response classes
from fastapi.responses import HTMLResponse

#template
from fastapi.templating import Jinja2Templates

#image upload
from fastapi import UploadFile, File
import secrets
from PIL import Image
from fastapi.staticfiles import StaticFiles 
import os



app = FastAPI()
BASE_URL = "https://easyshopas-api-production.up.railway.app"
SECRET = os.getenv("SECRET")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')



os.makedirs("static", exist_ok=True)
os.makedirs("static/images", exist_ok=True)
#static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/token")
async def generate_token(request_form: OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(request_form.username, request_form.password)
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = await User.get(id=payload.get("id"))
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

@app.post("/user/me")
async def user_login(user: User = Depends(get_current_user)):
    business = await Business.get(owner = user)
    logo = business.logo 
    logo_path = f"{BASE_URL}/static/images/{logo}"

    return{
        "status":"ok",
        "data":
        {
            "username": user.username,
            "email": user.email,
            "verified": user.is_verified,
            "joined_date": user.join_date.strftime("%b %d %Y"),
            "logo": logo_path
        }
    }



@post_save(User)
async def create_business(...):
    if created:
        business_obj = await Business.create(
            name=instance.username,
            owner=instance
        )

        await business_pydantic.from_tortoise_orm(business_obj)

        try:
            await send_email([instance.email], instance)
        except Exception as e:
            print("Email failed:", e)


@app.post("/registration/")
async def user_registration(user: user_pydanticIn): 
    user_info = user.dict(exclude_unset=True)
    user_info["password"] = get_hashed_password(user_info["password"])
    user_obj = await User.create(**user_info)
    new_user = await user_pydantic.from_tortoise_orm(user_obj)
    return {
        "status": "ok",
        "data": f"Hello {new_user.username}, thanks for choosing our services.please verify your email to start using our services"
    }

template = Jinja2Templates(directory="templates")

@app.get('/verification/', response_class=HTMLResponse)
async def email_verification(request: Request, token: str):
    user = await verify_token(token)

    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        return template.TemplateResponse(
            request=request,
            name="verification.html",
            context={"username": user.username}
        )
    elif user and user.is_verified:
        return template.TemplateResponse(
            request=request,
            name="verification.html",
            context={"username": user.username}
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token or expired token",
        headers={"WWW-Authenticate": "Bearer"}
    )

@app.get("/")
def index():
    return {"message": "hello world"}

@app.post("/uploadfile/profile")
async def upload_profile_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
    ):
    FILEPATH = "./static/images"
    filename = file.filename
    extension = filename.split(".")[-1].lower()
    if extension not in ["jpg", "jpeg", "png"]:
        return {"status": "error","detail": "Invalid file type. Only jpg, jpeg, and png are allowed."}
    token_name = secrets.token_hex(10)+"."+extension
    generate_name = f"{FILEPATH}/{token_name}"
    file_content = await file.read()
    with open(generate_name, "wb") as f:
        f.write(file_content)

    #PILLOW
    img = Image.open(generate_name)
    img = img.resize(size=(200, 200))
    img.save(generate_name)

    await file.close()

    business = await Business.get(owner = user)
    owner = await business.owner
    if owner.id == user.id:
        business.logo = token_name
        await business.save()
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action", headers={"WWW-Authenticate": "Bearer"})
    file_url = f"{BASE_URL}/static/images/{token_name}"
    return {"status": "ok", "filename": file_url}

@app.post("/uploadfile/product/{id}")
async def create_upload_file(id: int,file: UploadFile = File(...),user: User = Depends(get_current_user)):
    FILEPATH = "./static/images"
    filename = file.filename
    extension = filename.split(".")[1]
    if extension not in ["jpg", "jpeg", "png"]:
        return {"status": "error","detail": "Invalid file type. Only jpg, jpeg, and png are allowed."}
    token_name = secrets.token_hex(10)+"."+extension
    generate_name = f"{FILEPATH}/{token_name}"
    file_content = await file.read()
    with open(generate_name, "wb") as f:
        f.write(file_content)

    #PILLOW
    img = Image.open(generate_name)
    img = img.resize(size=(200, 200))
    img.save(generate_name)

    await file.close()

    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner
    if owner.id == user.id:
        product.product_image = token_name
        await product.save()
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action", headers={"WWW-Authenticate": "Bearer"})

    file_url = f"{BASE_URL}/static/images/{token_name}"
    return {"status": "ok", "filename": file_url}

#CRUD functionality
@app.post("/products")
async def add_new_product(product: product_pydanticIn, user: User = Depends(get_current_user)):
    product = product.dict(exclude_unset=True)
    if product["original_price"] > 0:
        product["percentage_discount"]=((product["original_price"] - product["new_price"])/product["original_price"])*100

        business = await Business.get(owner=user)

        product_obj = await Product.create(**product,business=business)
        product_obj = await product_pydantic.from_tortoise_orm(product_obj)

        return {"status": "ok", "data": product_obj}
    else:
        return {"status": "error", "detail": "Original price must be greater than zero"}
    

@app.get("/products")
async def get_products():
    response = await product_pydantic.from_queryset(Product.all())
    return {"status": "ok", "data": response}

@app.get("/products/{id}")
async def get_product(id: int):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner
    response = await product_pydantic.from_tortoise_orm(product)

    return{
        "status": "ok",
        "data": {
            "product_details": response,
            "business_details": {
                "name": business.name,
                "city": business.city,
                "region": business.region,
                "business_description": business.business_description,
                "logo": business.logo,
                "owner": owner.username,
                "email": owner.email,
                "join_date": owner.join_date.strftime("%b %d %Y")
            }
        }
    }

@app.delete("/products/{id}")
async def delete_product(id: int, user: User = Depends(get_current_user)):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner

    if owner.id == user.id:
        await product.delete()
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action", headers={"WWW-Authenticate": "Bearer"})
    return {"status": "ok", "detail": "Product deleted successfully"}

@app.put("/products/{id}")
async def update_product(id: int, update_info: product_pydanticIn, user: user_pydantic = Depends(get_current_user)):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner
    update_info = update_info.dict(exclude_unset=True)

    if user.id == owner.id and update_info["original_price"] > 0:
        update_info["percentage_discount"]=((update_info["original_price"] - update_info["new_price"])/update_info["original_price"])*100
        product = await product.update_from_dict(update_info)
        await product.save()
        response = await product_pydantic.from_tortoise_orm(product)
        return {"status": "ok", "data": response}
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action or invalid user input", headers={"WWW-Authenticate": "Bearer"})
    
@app.put("/business/{id}")
async def update_business(id: int, update_business: business_pydanticIn, user: user_pydantic = Depends(get_current_user)):
    update_business = update_business.dict()
    business = await Business.get(id=id)
    owner = await business.owner 
    if user.id == owner.id:    
        await business.update_from_dict(update_business)
        await business.save()
        response = await business_pydantic.from_tortoise_orm(business)
        return {"status": "ok", "data": response}
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized to perform this action", headers={"WWW-Authenticate": "Bearer"})

register_tortoise(
    app,
    db_url='sqlite://database.sqlite3',
    modules={'models': ['models']},
    generate_schemas=True,
    add_exception_handlers=True
)