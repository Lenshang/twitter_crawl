import os
import json
import math


def calc_score(jobj):
    results = []
    for item in jobj:
        view = int(item["views_count"])
        max_comment_view = 0
        for comment in item["comment"]:
            if int(comment["views_count"]) > max_comment_view:
                max_comment_view = int(comment["views_count"])
        results.append(max_comment_view / view)

    return round(sum(results) / len(results), 4)


if __name__ == "__main__":
    for item in os.listdir("./result"):
        name = item[: item.rfind(".")]
        # if name != "0xKillTheWolf":
        #     continue
        _path = os.path.join("./result", item)
        with open(_path, "r") as file:
            jobj = json.loads(file.read())
            score = calc_score(jobj)
            print(name + ":" + str(score))
