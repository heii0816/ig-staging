#!/usr/bin/env python3
"""
IG 排程發佈器 — 由 GitHub Actions 呼叫
每 15 分鐘檢查 schedule.json，時間到就立即發布
"""
import os, json, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

IG_API   = 'https://graph.instagram.com/v21.0'
TOKEN    = os.environ['IG_TOKEN']
USER_ID  = os.environ['IG_USER_ID']
TAIPEI   = timezone(timedelta(hours=8))

def ig_post(path, params):
    data = urllib.parse.urlencode(params).encode('utf-8')
    req  = urllib.request.Request(f'{IG_API}/{path}', data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'IG API {e.code}: {e.read().decode()}')

def publish(post):
    images  = post['images']
    caption = post.get('caption', '')

    if len(images) == 1:
        res = ig_post(f'{USER_ID}/media', {
            'image_url':    images[0],
            'caption':      caption,
            'access_token': TOKEN
        })
        container_id = res['id']
    else:
        ids = []
        for img_url in images:
            res = ig_post(f'{USER_ID}/media', {
                'image_url':        img_url,
                'is_carousel_item': 'true',
                'access_token':     TOKEN
            })
            ids.append(res['id'])
            time.sleep(1)
        res = ig_post(f'{USER_ID}/media', {
            'media_type':   'CAROUSEL',
            'caption':      caption,
            'children':     ','.join(ids),
            'access_token': TOKEN
        })
        container_id = res['id']

    time.sleep(4)
    result = ig_post(f'{USER_ID}/media_publish', {
        'creation_id':  container_id,
        'access_token': TOKEN
    })
    return result

def main():
    schedule_path = Path('schedule.json')
    if not schedule_path.exists():
        print('schedule.json not found, nothing to do.')
        return

    data    = json.loads(schedule_path.read_text(encoding='utf-8'))
    now     = datetime.now(timezone.utc)
    updated = False

    for post in data.get('posts', []):
        if post.get('status') != 'pending':
            continue

        sched_dt = datetime.fromisoformat(post['scheduled_time'])
        if sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=TAIPEI)

        if sched_dt > now:
            print(f"⏳ {post['id']}: {sched_dt.astimezone(TAIPEI).strftime('%Y-%m-%d %H:%M')} 台北時間，尚未到")
            continue

        print(f"→ 發布 {post['id']} ...")
        try:
            result = publish(post)
            post['status']       = 'published'
            post['published_at'] = datetime.now(TAIPEI).isoformat()
            post['ig_media_id']  = result.get('id', '')
            print(f"✓ 發布成功！ig_media_id={post['ig_media_id']}")
        except Exception as e:
            print(f"✗ 錯誤: {e}")
            post['status'] = 'error'
            post['error']  = str(e)
        updated = True

    if updated:
        schedule_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print('schedule.json 已更新')
    else:
        print('沒有需要發布的貼文')

if __name__ == '__main__':
    main()
