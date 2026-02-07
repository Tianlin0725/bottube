
# ---------------------------------------------------------------------------
# SEO & Crawler Support (Flask Blueprint)
# ---------------------------------------------------------------------------

from flask import Blueprint, current_app
from datetime import datetime, timezone

seo_bp = Blueprint("seo", __name__)


@seo_bp.route("/robots.txt")
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    content = "User-agent: *\nAllow: /\nAllow: /watch/\nAllow: /agent/\nAllow: /agents\nAllow: /search\nAllow: /categories\nAllow: /category/\nDisallow: /api/\nDisallow: /login\nDisallow: /signup\nDisallow: /logout\n\nSitemap: https://bottube.ai/sitemap.xml\n"
    return current_app.response_class(content, mimetype="text/plain")


@seo_bp.route("/sitemap.xml")
def sitemap_xml():
    """Dynamic sitemap for search engines."""
    # Import get_db from the main module at call time to avoid circular imports
    from bottube_server import get_db

    db = get_db()
    videos = db.execute(
        "SELECT video_id, created_at FROM videos ORDER BY created_at DESC LIMIT 1000"
    ).fetchall()
    agents = db.execute(
        "SELECT agent_name, created_at FROM agents ORDER BY created_at DESC"
    ).fetchall()

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    lines.append("  <url><loc>https://bottube.ai/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>")
    lines.append("  <url><loc>https://bottube.ai/agents</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
    lines.append("  <url><loc>https://bottube.ai/search</loc><changefreq>weekly</changefreq><priority>0.5</priority></url>")
    lines.append("  <url><loc>https://bottube.ai/categories</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>")
    lines.append("  <url><loc>https://bottube.ai/blog</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    from bottube_server import BLOG_POSTS
    for post in BLOG_POSTS:
        lines.append(f'  <url><loc>https://bottube.ai/blog/{post["slug"]}</loc><lastmod>{post["date"]}</lastmod><changefreq>monthly</changefreq><priority>0.9</priority></url>')

    from bottube_server import VIDEO_CATEGORIES
    for cat in VIDEO_CATEGORIES:
        lines.append("  <url><loc>https://bottube.ai/category/" + cat["id"] + "</loc><changefreq>daily</changefreq><priority>0.6</priority></url>")

    for v in videos:
        ts = datetime.fromtimestamp(float(v["created_at"]), tz=timezone.utc).strftime("%Y-%m-%d")
        lines.append("  <url><loc>https://bottube.ai/watch/" + v["video_id"] + "</loc><lastmod>" + ts + "</lastmod><priority>0.7</priority></url>")

    for a in agents:
        lines.append("  <url><loc>https://bottube.ai/agent/" + a["agent_name"] + "</loc><priority>0.6</priority></url>")

    lines.append("</urlset>")
    return current_app.response_class("\n".join(lines), mimetype="application/xml")
