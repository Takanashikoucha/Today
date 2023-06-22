# -*- coding: utf8 -*-
# @LastAuthor: TakanashiKoucha
# @Date: 2022-03-26 22:30:33
import datetime
import sxtwl


lunarYear = 0


def toLunar(a, b, c):
    global lunarYear
    day = sxtwl.fromSolar(a, b, c)
    s = "<h2> 农历:%d年%s%d月%d日 </h2>\n" % (day.getLunarYear(),
                                         '闰' if day.isLunarLeap() else '', day.getLunarMonth(), day.getLunarDay())
    lunarYear = day.getLunarYear()
    return s


def birth(a, b):
    global lunarYear
    day = sxtwl.fromLunar(lunarYear, a, b)
    s = " ：<b> %d年%d月%d日 </b>" % (
        day.getSolarYear(), day.getSolarMonth(), day.getSolarDay())
    today = datetime.datetime(datetime.date.today(
    ).year, datetime.date.today().month, datetime.date.today().day)
    d1 = datetime.datetime(
        day.getSolarYear(), day.getSolarMonth(), day.getSolarDay())
    num = d1-today
    if num.days >= 0:
        s = s+"还有%d  天 </p>\n" % (num.days)
    if num.days < 0:
        s = s+"已过%d  天 </p>\n" % (num.days)
    return s


def newbirth(a, b):
    s = ""
    today = datetime.datetime(datetime.date.today(
    ).year, datetime.date.today().month, datetime.date.today().day)
    d1 = datetime.datetime(datetime.date.today(
    ).year, a, b)
    num = d1-today
    if num.days >= 0:
        s = s+"还有%d  天 </p>\n" % (num.days)
    if num.days < 0:
        s = s+"已过%d  天 </p>\n" % (num.days)
    return s


def main():
    log = ""
    log = log + "<h1> 今天是:  "+str(datetime.date.today().year)+" 年 " + str(
        datetime.date.today().month)+" 月 " + str(datetime.date.today().day)+" 日 </h1>\n"
    log = log + toLunar(datetime.date.today().year,
                        datetime.date.today().month, datetime.date.today().day)
    log = log + "<p> <b>苏天成</b>  九月二十一 " + birth(9, 21)
    log = log + "<p> <b>林贞玉</b>   十二月十一 " + birth(12, 11)
    log = log + "<p> <b>陈春花</b>  二月初六 " + birth(2, 6)
    log = log + "<p> <b>苏发金</b>  八月初六 " + birth(8, 6)
    log = log + "<p> <b>苏金仙</b>  二月十八 " + birth(2, 18)
    log = log + "<p> <b>张学将</b>  十月初十 " + birth(10, 10)
    log = log + "<p> <b>杨通慧</b>  正月二十二 " + birth(1, 22)
    log = log + "<p> <b>苏发银</b>  十月十九 " + birth(10, 19)
    log = log + "<p> <b>余燕</b>  八月十五 " + birth(8, 15)
    log = log + "<p> <b>苏首峰</b>  十月二十四 " + birth(10, 24)
    log = log + "<p> <b>张若燕</b>  新历 五月三 " + newbirth(5, 3)
    log = log + "<p> <b>张建</b>   八月二十九 " + birth(8, 29)
    log = log + "<p> <b>滕勇</b>   二月初七 " + birth(2, 7)
    log = log + "<p> <b>苏江庆</b>  新历 四月十 " + newbirth(4, 10)
    log = log + "<p> <b>苏江鹏</b>  五月十四 " + birth(5, 14)
    log = log + "<p> <b>王亚君</b>  七月二十一 " + birth(7, 21)
    log = log + "<p> <b>张若鹏</b>  新历 二月十三 " + newbirth(2, 13)
    log = log + "<p> <b>苏温昕</b>  八月二十三 " + birth(8, 23)
    log = log + "<p> <b>苏卓恩</b>  十月二十三 " + birth(10, 23)
    log = log + "<p> <b>苏元航</b>  二月二十 " + birth(2, 20)
    log = log + "<p> <b>张辰玥</b>  新历 五月十八 " + birth(5, 18)
    return log


if __name__ == "__main__":
    main()
