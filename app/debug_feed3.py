import sys
sys.path.insert(0, r"C:\Users\GLOW\Desktop\Code Projects\Coding Planning\app")
import combined

posts = combined.fetch_discord_freebies()
print(f"Returned {len(posts)} posts")
for p in posts[:10]:
    print(f"  {p.get('casino_name', '?'):20s} | {p.get('url', '')[:70]}")
