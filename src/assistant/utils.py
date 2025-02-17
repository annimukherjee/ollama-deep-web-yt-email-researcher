import os
import requests
from typing import Dict, Any
from langsmith import traceable
from tavily import TavilyClient

def deduplicate_and_format_sources(search_response, max_tokens_per_source, include_raw_content=False):
    """
    Takes either a single search response or list of responses from search APIs and formats them.
    Limits the raw_content to approximately max_tokens_per_source.
    include_raw_content specifies whether to include the raw_content from Tavily in the formatted string.
    
    Args:
        search_response: Either:
            - A dict with a 'results' key containing a list of search results
            - A list of dicts, each containing search results
            
    Returns:
        str: Formatted string with deduplicated sources
    """
    # Convert input to list of results
    if isinstance(search_response, dict):
        sources_list = search_response['results']
    elif isinstance(search_response, list):
        sources_list = []
        for response in search_response:
            if isinstance(response, dict) and 'results' in response:
                sources_list.extend(response['results'])
            else:
                sources_list.extend(response)
    else:
        raise ValueError("Input must be either a dict with 'results' or a list of search results")
    
    # Deduplicate by URL
    unique_sources = {}
    for source in sources_list:
        if source['url'] not in unique_sources:
            unique_sources[source['url']] = source
    
    # Format output
    formatted_text = "Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"Source {source['title']}:\n===\n"
        formatted_text += f"URL: {source['url']}\n===\n"
        formatted_text += f"Most relevant content from source: {source['content']}\n===\n"
        if include_raw_content:
            # Using rough estimate of 4 characters per token
            char_limit = max_tokens_per_source * 4
            # Handle None raw_content
            raw_content = source.get('raw_content', '')
            if raw_content is None:
                raw_content = ''
                print(f"Warning: No raw_content found for source {source['url']}")
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
                
    return formatted_text.strip()

def format_sources(search_results):
    """Format search results into a bullet-point list of sources.
    
    Args:
        search_results (dict): Search response containing results
        
    Returns:
        str: Formatted string with sources and their URLs
    """
    return '\n'.join(
        f"* {source['title']} : {source['url']}"
        for source in search_results['results']
    )

@traceable
def tavily_search(query, include_raw_content=True, max_results=3):
    """ Search the web using the Tavily API.
    
    Args:
        query (str): The search query to execute
        include_raw_content (bool): Whether to include the raw_content from Tavily in the formatted string
        max_results (int): Maximum number of results to return
        
    Returns:
        dict: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result
                - url (str): URL of the search result
                - content (str): Snippet/summary of the content
                - raw_content (str): Full content of the page if available"""
     
    tavily_client = TavilyClient()
    return tavily_client.search(query, 
                         max_results=max_results, 
                         include_raw_content=include_raw_content)

@traceable
def perplexity_search(query: str, perplexity_search_loop_count: int) -> Dict[str, Any]:
    """Search the web using the Perplexity API.
    
    Args:
        query (str): The search query to execute
        perplexity_search_loop_count (int): The loop step for perplexity search (starts at 0)
  
    Returns:
        dict: Search response containing:
            - results (list): List of search result dictionaries, each containing:
                - title (str): Title of the search result
                - url (str): URL of the search result
                - content (str): Snippet/summary of the content
                - raw_content (str): Full content of the page if available
    """

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}"
    }
    
    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": "Search the web and provide factual information with sources."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=payload
    )
    response.raise_for_status()  # Raise exception for bad status codes
    
    # Parse the response
    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Perplexity returns a list of citations for a single search result
    citations = data.get("citations", ["https://perplexity.ai"])
    
    # Return first citation with full content, others just as references
    results = [{
        "title": f"Perplexity Search {perplexity_search_loop_count + 1}, Source 1",
        "url": citations[0],
        "content": content,
        "raw_content": content
    }]
    
    # Add additional citations without duplicating content
    for i, citation in enumerate(citations[1:], start=2):
        results.append({
            "title": f"Perplexity Search {perplexity_search_loop_count + 1}, Source {i}",
            "url": citation,
            "content": "See above for full content",
            "raw_content": None
        })
    
    return {"results": results}


from concurrent.futures import ThreadPoolExecutor, TimeoutError

def get_transcript_with_timeout(video_id, timeout=10):
    from youtube_transcript_api import YouTubeTranscriptApi
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(YouTubeTranscriptApi.get_transcript, video_id)
        try:
            transcript_data = future.result(timeout=timeout)
            return " ".join([segment["text"] for segment in transcript_data])
        except TimeoutError:
            return "Transcript retrieval timed out."
        except Exception as e:
            return "Transcript not available."


# @traceable
# def youtube_search(query: str, youtube_api_key: str, max_results: int = 3) -> Dict[str, Any]:
#     """Search YouTube for videos matching the query and fetch their transcripts.
    
#     Args:
#         query (str): The search query to execute.
#         youtube_api_key (str): API key for YouTube Data API.
#         max_results (int): Maximum number of videos to return.
        
#     Returns:
#         dict: Search response containing:
#             - results (list): List of video dictionaries, each containing:
#                 - title (str): Title of the video
#                 - url (str): URL of the video
#                 - content (str): A snippet of the transcript
#                 - raw_content (str): Full transcript if available
#     """
#     search_url = "https://www.googleapis.com/youtube/v3/search"
#     params = {
#          "part": "snippet",
#          "q": query,
#          "type": "video",
#          "maxResults": max_results,
#          "key": youtube_api_key,
#     }
#     response = requests.get(search_url, params=params, timeout=10)
#     response.raise_for_status()
#     data = response.json()
#     results = []
#     for item in data.get("items", []):
#          video_id = item["id"]["videoId"]
#          title = item["snippet"]["title"]
#          url = f"https://www.youtube.com/watch?v={video_id}"
#          # Attempt to fetch the transcript
#          transcript = ""
#          try:
#              from youtube_transcript_api import YouTubeTranscriptApi
#              transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
#              transcript = " ".join([segment["text"] for segment in transcript_data])
#          except Exception as e:
#              transcript = "Transcript not available."
#          result = {
#              "title": title,
#              "url": url,
#              "content": transcript[:200] + "..." if len(transcript) > 200 else transcript,
#              "raw_content": transcript,
#          }
#          results.append(result)
#     return {"results": results}

@traceable
def youtube_search(query: str, youtube_api_key: str, max_results: int = 3) -> Dict[str, Any]:
    """Search YouTube for videos matching the query and fetch their transcripts."""
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
         "part": "snippet",
         "q": query,
         "type": "video",
         "maxResults": max_results,
         "key": youtube_api_key,
    }
    # Add a timeout here as well
    response = requests.get(search_url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("items", []):
         video_id = item["id"]["videoId"]
         title = item["snippet"]["title"]
         url = f"https://www.youtube.com/watch?v={video_id}"
         # Use the helper function for transcript retrieval with a timeout
         transcript = get_transcript_with_timeout(video_id, timeout=10)
         result = {
             "title": title,
             "url": url,
             "content": transcript[:200] + "..." if len(transcript) > 200 else transcript,
             "raw_content": transcript,
         }
         results.append(result)
    return {"results": results}