import asyncio
import json
import os
import dateutil
import time
import zmq
import queue
import sys
import socket as _socket
from multiprocessing import Process
from playwright.async_api import async_playwright, Page, Browser, Route, Response
from playwright_stealth import stealth_async
from ExObject.DateTime import DateTime
import config as cfg


async def twitterCookieGen():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, proxy={"server": "127.0.0.1:7890"})
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://x.com/")
        await asyncio.sleep(10)
        name = input("press enter to save cookie->file_name:")
        await asyncio.sleep(10)
        storage = await context.storage_state(path=f"account/{name}.json")
    print("save success")


if __name__ == "__main__":
    asyncio.run(twitterCookieGen())
