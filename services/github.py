import base64
import json
import httpx
from config import GITHUB_REPO, GITHUB_TOKEN, GITHUB_BRANCH, DNS_SERVERS

async def get_categories_from_github() -> list[str]:
    """Get list of category folders from GitHub repo config/ directory."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/config"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        response.raise_for_status()
        
    contents = response.json()
    categories = [item["name"] for item in contents if item["type"] == "dir"]
    return categories

def create_site_json(domain: str, ip4: list[str], ip6: list[str]) -> dict:
    """Create JSON structure for the site."""
    return {
        "domains": [domain, f"www.{domain}"],
        "dns": DNS_SERVERS,
        "timeout": 3600,
        "ip4": ip4,
        "ip6": ip6,
        "cidr4": [],
        "cidr6": [],
        "external": {
            "domains": [],
            "ip4": [],
            "ip6": [],
            "cidr4": [],
            "cidr6": []
        }
    }

async def create_file_in_github(category: str, domain: str, content: dict) -> tuple[str, str]:
    """Create a new file in the GitHub repository."""
    file_path = f"config/{category}/{domain}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    
    json_content = json.dumps(content, indent=4)
    encoded_content = base64.b64encode(json_content.encode()).decode()
    
    data = {
        "message": f"feat({category}): add {domain}",
        "content": encoded_content,
        "branch": GITHUB_BRANCH
    }
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        # Check if file exists to update sha
        try:
            get_response = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            if get_response.status_code == 200:
                sha = get_response.json().get("sha")
                data["sha"] = sha
                data["message"] = f"fix({category}): update {domain}"
        except httpx.HTTPError:
            pass
            
        response = await client.put(url, headers=headers, json=data)
        response.raise_for_status()
        
    result = response.json()
    html_url = result["content"]["html_url"]
    commit_sha = result["commit"]["sha"]
    return html_url, commit_sha
