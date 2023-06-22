# -*- coding: utf8 -*-
# @LastAuthor: TakanashiKoucha
# @Date: 2022-03-27 01:30:04
import todayDate
import metal

from fastapi import FastAPI

app = FastAPI()
body = ""


def gen_body():
    body = ""
    body = body + str(todayDate.main())
    body = body + "\n<hr>\n"
    body = body + str(metal.main())
    body = body + "\n<hr>\n"
    return body


@app.get("/")
def read_root():
    return gen_body()
