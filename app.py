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
    body = """<!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <title>Today</title>
            </head>
            <body>"""
    body = body + str(todayDate.main())
    body = body + "\n<hr>\n"
#    body = body + str(metal.main())
    body = body + "\n<hr>\n"
    body = (
        body
        + """</body>
            </html>"""
    )
    return body


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=gen_body(), status_code=200)
