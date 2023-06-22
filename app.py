# -*- coding: utf8 -*-
# @LastAuthor: TakanashiKoucha
# @Date: 2022-03-27 01:30:04
import todayDate
import metal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()
body = ""


def gen_body():
    body = ""
    body = body + str(todayDate.main())
    body = body + "\n<hr>\n"
    body = body + str(metal.main())
    body = body + "\n<hr>\n"
    return body


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=gen_body(), status_code=200)
