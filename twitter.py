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

before_7day = DateTime.Now().AddDays(-7).TimeStampLong()
lock = asyncio.Lock()
twitter_list = {}
current_id = None


def zmq_server():
    task = queue.Queue()
    with open("task.txt", "r") as file:
        for url in file.readlines():
            user_name = url.split("/")[-1]
            if os.path.exists(f"result/{user_name.strip()}.json"):
                continue
            if url.strip():
                task.put(url.strip())
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://127.0.0.1:" + str(cfg.ZMQ_PORT))
    print("[BF_SERVICE_ZMQ] Service Start...")
    while True:
        try:
            # print("wait for client ...")
            message = socket.recv().decode("utf-8")
            if message == "ping":
                socket.send("pong".encode("utf-8"))
                continue
            # print("[BF_SERVICE_ZMQ] message from client:", message.decode("utf-8"))
            try:
                if message == "task":
                    ret = task.get()
                    socket.send(ret.encode("utf-8"))
            except Exception as e:
                pass
        except Exception as e:
            print("[BF_SERVICE_ZMQ] 异常:", e)
            break


def create_zmq():

    def is_port_open():
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", cfg.ZMQ_PORT)) == 0

    # 判断端口占用情况，如果指定端口未被占用，则启动zmq_server
    if not is_port_open():
        p = Process(target=zmq_server)
        p.start()
        time.sleep(3)

    context = zmq.Context(2)
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://127.0.0.1:" + str(cfg.ZMQ_PORT))

    def get_task():
        socket.send("task".encode("utf-8"))
        return socket.recv().decode("utf-8")

    while True:
        yield get_task()


async def twitterCrawl(url, cookie_name="xslsa77675247"):
    user_name = url.split("/")[-1]
    global twitter_list
    global current_id
    twitter_list = {}
    current_id = None

    def twitter_list_handler(body):
        global twitter_list
        jObj = json.loads(body)
        try:

            def get_timeline():
                for item in jObj["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]:
                    if item["type"] == "TimelineAddEntries":
                        return item["entries"]

            for item in get_timeline():
                try:
                    id = item["entryId"]
                    if "tweet-" not in id:
                        continue
                    pub_date = item["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["created_at"]
                    pub_date = int(dateutil.parser.parse(pub_date).timestamp()) * 1000
                    if item["content"]["itemContent"]["tweet_results"]["result"]["legacy"].get("retweeted_status_result"):
                        continue
                    v_count = item["content"]["itemContent"]["tweet_results"]["result"]["views"].get("count")
                    if v_count == None:
                        continue
                    reply_count = int(item["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["reply_count"])
                    if reply_count < 2:
                        continue
                    if pub_date < before_7day:
                        data = {
                            "id": id.split("-")[1],
                            "pub_date": pub_date,
                            "views_count": v_count,
                            "content": item["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["full_text"],
                            "reply_count": reply_count,
                            "retweet_count": item["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["retweet_count"],
                            "favorite_count": item["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["favorite_count"],
                            "comment": [],
                        }
                        twitter_list[data["id"]] = data
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)

    def twitter_detail_handler(body):
        global twitter_list
        global current_id
        jObj = json.loads(body)

        def get_timeline():
            for item in jObj["data"]["threaded_conversation_with_injections_v2"]["instructions"]:
                if item["type"] == "TimelineAddEntries":
                    return item["entries"]

        id = current_id
        for item in get_timeline():
            try:
                if "conversationthread-" not in item["entryId"]:
                    continue
                content = None
                try:
                    content = item["content"]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
                except:
                    continue
                if not content.get("legacy"):
                    continue
                pub_date = content["legacy"]["created_at"]
                pub_date = int(dateutil.parser.parse(pub_date).timestamp()) * 1000

                v_count = content["views"].get("count")
                if v_count == None:
                    continue

                data = {
                    "user_id": content["legacy"]["user_id_str"],
                    "content": content["legacy"]["full_text"],
                    "views_count": v_count,
                    "pub_date": pub_date,
                }
                twitter_list[id]["comment"].append(data)
            except Exception as e:
                print(e)

    async def intercept_response(response: Response):
        # print("resp:" + response.url)
        if "UserTweets" in response.url:
            # print("fetch user tweet")
            body = await response.body()
            twitter_list_handler(body.decode("utf-8"))
        elif "TweetDetail" in response.url:
            # print("fetch tweet detail")
            body = await response.body()
            async with lock:
                twitter_detail_handler(body.decode("utf-8"))
        return response

    async with async_playwright() as p:
        if cfg.PROXY:
            browser = await p.chromium.launch(headless=cfg.HEADLESS, proxy={"server": cfg.PROXY})
        else:
            browser = await p.chromium.launch(headless=cfg.HEADLESS)
        context = await browser.new_context(viewport={"width": 1600, "height": 900}, storage_state=f"account/{cookie_name}.json")
        page = await context.new_page()
        await stealth_async(page)
        # await page.route("**/*.{png,jpg,jpeg,css,woff2,gif,mp4,avi,flv}", lambda route: route.abort())
        page.on("response", intercept_response)
        await page.goto(url)

        await asyncio.sleep(3)
        st = DateTime.Now()
        while len(twitter_list.keys()) < 10:
            try:
                await page.locator('//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/section').hover()
            except:
                # 定位不到可能该账户存在问题 抛出异常
                print(url + ":error!")
                return
            await page.mouse.wheel(0, 3000)
            await asyncio.sleep(3)
            if (DateTime.Now() - st).TotalSecond > 180:
                # 超过3分钟没抓到数据，退出
                break
        # 抓取评论
        final_result = []
        c = 0
        for id in twitter_list.keys():
            current_id = id
            _url = f"https://x.com/{user_name}/status/" + id
            await page.goto(_url)
            await asyncio.sleep(10)
            st = DateTime.Now()
            has_comment = False
            while (DateTime.Now() - st).TotalSecond < 15:
                await asyncio.sleep(1)
                async with lock:
                    if len(twitter_list[id]["comment"]) > 0:
                        has_comment = True
                        break
            if has_comment:
                final_result.append(twitter_list[id])
                c += 1
                if c > 5:
                    break
        storage = await context.storage_state(path=f"account/{cookie_name}.json")
        with open(f"result/{user_name}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(final_result))

        print(user_name + " OK!")


if __name__ == "__main__":
    if not os.path.exists("./result"):
        os.makedirs("./result")
    account_name = sys.argv[1]
    for url in create_zmq():
        user_name = url.split("/")[-1]
        if os.path.exists(f"result/{user_name.strip()}.json"):
            continue
        if url.strip():
            asyncio.run(twitterCrawl(url.strip(), account_name))
            time.sleep(60)

    # with open("task.txt", "r") as file:
    #     for url in file.readlines():
    #         user_name = url.split("/")[-1]
    #         if os.path.exists(f"result/{user_name.strip()}.json"):
    #             continue
    #         if url.strip():
    #             asyncio.run(twitterCrawl(url.strip(), account_name))
    #             time.sleep(60)

    # asyncio.run(twitterCrawl("https://x.com/aibaaiai", "xslsa77675247"))
