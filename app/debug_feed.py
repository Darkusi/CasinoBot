import requests, json, re, sys
sys.path.insert(0, r"C:\Users\GLOW\Desktop\Code Projects\Coding Planning\app")
import combined

# Test 1: Discord API
print("=== Test 1: Discord API ===")
cid = combined.DISCORD_CHANNEL_ID
token = combined.DISCORD_BOT_TOKEN
print(f"Channel: {cid}")
print(f"Token: {token[:20]}...")

headers = {"Authorization": f"Bot {token}"}
url = f"https://discord.com/api/v10/channels/{cid}/messages"
resp = requests.get(url, headers=headers, params={"limit": 10}, timeout=10)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    msgs = resp.json()
    print(f"Messages: {len(msgs)}")
    for m in msgs[:5]:
        c = m.get("content", "")
        print(f"  ID={m['id']} content='{c[:100]}'")
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', c)
        print(f"  URLs: {urls}")
else:
    print(resp.text[:500])

# Test 2: fetch_discord_freebies
print("\n=== Test 2: fetch_discord_freebies ===")
posts = combined.fetch_discord_freebies()
print(f"Returned {len(posts)} posts")
for p in posts[:3]:
    print(f"  {p.get('casino_name')}: {p.get('url', '')[:60]}")

# Test 3: fetch_daily_freebies (Reddit)
print("\n=== Test 3: fetch_daily_freebies ===")
posts2 = combined.fetch_daily_freebies()
print(f"Returned {len(posts2)} posts")
for p in posts2[:3]:
    print(f"  {p.get('casino_name')}: {p.get('url', '')[:60]}")
