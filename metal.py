# -*- coding: utf8 -*-
# @LastAuthor: TakanashiKoucha
# @Date: 2022-03-26 19:14:56

import requests
from lxml import etree


def main():
    log = ""
    # 黄金部分
    gold_url = "http://www.kitco.cn/KitcoDynamicSite/RequestHandler?requestName=getFileContent&AttributeId=GoldSpotPrice"
    gold_web = requests.get(url=gold_url)
    gold_paser = etree.HTML(gold_web.text)
    renewDate = gold_paser.xpath(
        '''/html/body/div/table/tr[8]/td/font/text()''')
    auin = gold_paser.xpath(
        '''/html/body/div/table/tr[3]/td[3]/font/text()''')
    auout = gold_paser.xpath(
        '''/html/body/div/table/tr[3]/td[4]/font/text()''')
    log = log+str("<p> 数据更新时间：  "+renewDate[0].strip() +
                  "<p>\n<p> 黄金买入：  "+auin[0]+"  黄金卖出：  "+auout[0])
    # 白银，铂，钯
    url = "http://www.kitco.cn/KitcoDynamicSite/RequestHandler?requestName=getFileContent&AttributeId=SilverPGMPricesCNY"
    web = requests.get(url=url)
    paser = etree.HTML(web.text)
    sl = paser.xpath('''/html/body/div/table/tr[3]/td[3]/text()''')
    pt = paser.xpath('''/html/body/div/table/tr[4]/td[3]/text()''')
    pd = paser.xpath('''/html/body/div/table/tr[5]/td[3]/text()''')
    log = log+str("<p>\n<p> 白银价格：  "+sl[0])
    log = log+str("<p>\n<p> 铂金价格：  "+pt[0])
    log = log+str("<p>\n<p> 钯金价格：  "+pd[0]+" <p>")
    return log


if __name__ == "__main__":
    main()
