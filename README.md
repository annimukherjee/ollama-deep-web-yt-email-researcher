# ollama-deep-web-yt-email-researcher
 
## 🚀 Quickstart

### Mac 

1. Download the Ollama app for Mac [here](https://ollama.com/download).

2. Pull a local LLM from [Ollama](https://ollama.com/search). As an [example](https://ollama.com/library/deepseek-r1:8b): 
```bash
ollama pull deepseek-r1:8b
```

3. Clone the repository:
```bash
git clone https://github.com/annimukherjee/ollama-deep-web-yt-email-researcher
cd ollama-deep-web-yt-email-researcher
```

4. Select a web search tool:

* [Tavily API](https://tavily.com/)
* [Perplexity API](https://www.perplexity.ai/hub/blog/introducing-the-sonar-pro-api)
* [YouTube API](https://www.getphyllo.com/post/how-to-get-youtube-api-key)

5. Copy the example environment file:
```bash
cp .env.example .env
```

6. Edit the `.env` file with your preferred text editor and add your API keys:
```bash
# Required: Choose one search provider and add its API key
TAVILY_API_KEY=tvly-xxxxx      # Get your key at https://tavily.com
PERPLEXITY_API_KEY=pplx-xxxxx  # Get your key at https://www.perplexity.ai
PERPLEXITY_API_KEY=pplx-xxxxx  # Get your key at https://www.perplexity.ai
SMTP_USERNAME=xxxx@gmail.com   # The email you will send from
SMTP_PASSWORD=xxxx             # Get your app password from https://myaccount.google.com/apppasswords
EMAIL_RECIPIENT=xxxx@gmail.com  # The email that will receive the summary
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=xxxx               # Port for Email Application
YOUTUBE_API_KEY=xxxx          # Get your key at https://www.getphyllo.com/post/how-to-get-youtube-api-key
```


**Note: Also copy these same keys to the `configuration.py` file present in the `src/assistant` directory.** 

Note: If you prefer using environment variables directly, you can set them in your shell:
```bash
export TAVILY_API_KEY=tvly-xxxxx
# OR
export PERPLEXITY_API_KEY=pplx-xxxxx
```

After setting the keys, verify they're available:
```bash
echo $TAVILY_API_KEY  # Should show your API key
```

7. (Recommended) Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

8. Launch the assistant with the LangGraph server:

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev
```

### Windows 

1. Download the Ollama app for Windows [here](https://ollama.com/download).

2. Pull a local LLM from [Ollama](https://ollama.com/search). As an [example](https://ollama.com/library/deepseek-r1:8b): 
```powershell
ollama pull deepseek-r1:8b
```

3. Clone the repository:
```bash
git clone https://github.com/annimukherjee/ollama-deep-web-yt-email-researcher
cd ollama-deep-web-yt-email-researcher
```
 
4. Select a web search tool:

* [Tavily API](https://tavily.com/)
* [Perplexity API](https://www.perplexity.ai/hub/blog/introducing-the-sonar-pro-api)

5. Copy the example environment file:
```bash
cp .env.example .env
```

Edit the `.env` file with your preferred text editor and add your API keys:
```bash
# Required: Choose one search provider and add its API key
TAVILY_API_KEY=tvly-xxxxx      # Get your key at https://tavily.com
PERPLEXITY_API_KEY=pplx-xxxxx  # Get your key at https://www.perplexity.ai
PERPLEXITY_API_KEY=pplx-xxxxx  # Get your key at https://www.perplexity.ai
SMTP_USERNAME=xxxx@gmail.com   # The email you will send from
SMTP_PASSWORD=xxxx             # Get your app password from https://myaccount.google.com/apppasswords
EMAIL_RECIPIENT=xxxx@gmail.com  # The email that will receive the summary
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=xxxx               # Port for Email Application
YOUTUBE_API_KEY=xxxx          # Get your key at https://www.getphyllo.com/post/how-to-get-youtube-api-key
```

Note: If you prefer using environment variables directly, you can set them in Windows (via System Properties or PowerShell):

```bash
export TAVILY_API_KEY=<your_tavily_api_key>
export PERPLEXITY_API_KEY=<your_perplexity_api_key>
```

Crucially, restart your terminal/IDE (or sometimes even your computer) after setting it for the change to take effect. After setting the keys, verify they're available:
```bash
echo $TAVILY_API_KEY  # Should show your API key
```

7. (Recommended) Create a virtual environment: Install `Python 3.11` (and add to PATH during installation). Restart your terminal to ensure Python is available, then create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

8. Launch the assistant with the LangGraph server:

```powershell
# Install dependencies 
pip install -e .
pip install langgraph-cli[inmem]

# Start the LangGraph server
langgraph dev
```

### Using the LangGraph Studio UI 

When you launch LangGraph server, you should see the following output and Studio will open in your browser:
> Ready!
> 
> API: http://127.0.0.1:2024
> 
> Docs: http://127.0.0.1:2024/docs
> 
> LangGraph Studio Web UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024

Open `LangGraph Studio Web UI` via the URL in the output above. 

In the `configuration` tab:
* Pick your web search tool (Tavily or Perplexity) (it will by default be `Tavily`) 
* Set the name of your local LLM to use with Ollama (it will by default be `llama3.2`) 
* You can set the depth of the research iterations (it will by default be `3`)

Give the assistant a topic for research, and you can visualize its process!


## How it works

Ollama Deep Researcher is inspired by [IterDRAG](https://arxiv.org/html/2410.04343v1#:~:text=To%20tackle%20this%20issue%2C%20we,used%20to%20generate%20intermediate%20answers.). This approach will decompose a query into sub-queries, retrieve documents for each one, answer the sub-query, and then build on the answer by retrieving docs for the second sub-query. Here, we do similar:
- Given a user-provided topic, use a local LLM (via [Ollama](https://ollama.com/search)) to generate a web search query
- Uses a search engine (configured for [Tavily](https://www.tavily.com/)) to find relevant sources
- Uses LLM to summarize the findings from web search related to the user-provided research topic
- Then, it uses the LLM to reflect on the summary, identifying knowledge gaps
- It generates a new search query to address the knowledge gaps
- The process repeats, with the summary being iteratively updated with new information from web search
- It will repeat down the research rabbit hole 
- Runs for a configurable number of iterations (see `configuration` tab)  

## Outputs

The output of the graph is a markdown file emailed to your email of choice containing the research summary, with citations to the sources used.

All sources gathered during research are saved to the graph state. 

You can visualize them in the graph state, which is visible in LangGraph Studio:

![grab-Studio - LangSmith--Google Chrome_at_15 34 24_on__27-02-2025__003670](https://github.com/user-attachments/assets/69b08847-689a-4e1e-8805-7d77bae0d1b2)

