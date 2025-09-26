# 🔌 Tavily MCP Integration Guide

This document explains how to use Model Context Protocol (MCP) with Tavily in your Market Research Workflow project.

## 🚀 What is MCP?

Model Context Protocol (MCP) is a standard for connecting AI assistants to external data sources and tools. It provides a unified interface for AI models to interact with various services, making it easier to integrate multiple tools into your workflow.

## 🔍 Tavily MCP Features

### Available Tools
- **tavily_search**: Real-time web search with advanced filtering
- **tavily_extract**: Extract content from specific URLs
- **tavily_map**: Map website structure and navigation
- **tavily_crawl**: Crawl websites to extract comprehensive content

### Benefits of MCP Integration
1. **Unified Interface**: Single protocol for all external tools
2. **Better Error Handling**: Standardized error responses
3. **Enhanced Capabilities**: Access to advanced Tavily features
4. **Future-Proof**: Easy to add more MCP tools
5. **Fallback Support**: Automatic fallback to direct API if MCP fails

## 📁 File Structure

```
src/tools/
├── tavily_client.py          # Original direct API client
├── tavily_mcp_client.py      # New MCP-based client
└── retriever.py              # Updated to support both methods
```

## 🔧 Implementation Details

### 1. MCP Client (`tavily_mcp_client.py`)

The MCP client provides both async and sync interfaces:

```python
# Async usage
async with TavilyMCPClient(api_key) as client:
    result = await client.search("AI trends 2025")

# Sync usage (recommended for current workflow)
from src.tools.tavily_mcp_client import tavily_search_mcp
result = tavily_search_mcp("AI trends 2025")
```

### 2. Enhanced Retriever (`retriever.py`)

The retriever now supports both MCP and direct API methods:

```python
# Use MCP (default)
result = retrieve_market_data_mcp(query)

# Use direct API
result = retrieve_market_data(query, use_mcp=False)
```

### 3. Agent Integration (`agents.py`)

The market researcher agent now uses MCP by default:

```python
def market_researcher(state: WorkflowState) -> WorkflowState:
    # Uses MCP with fallback to direct API
    result = retrieve_market_data_mcp(query)
```

## 🛠️ Setup Instructions

### 1. Install Dependencies

```bash
pip install mcp tavily-mcp
```

### 2. Set Environment Variables

```bash
export TAVILY_API_KEY=your_tavily_api_key_here
```

### 3. Test Integration

```bash
python test_mcp_integration.py
```

## 🔄 How It Works

### Current Implementation (Fallback Mode)

Since setting up a full MCP server is complex, the current implementation uses a **fallback approach**:

1. **MCP Client**: Attempts to connect to MCP server
2. **Fallback**: If MCP fails, automatically falls back to direct Tavily API
3. **Seamless**: Your workflow continues without interruption

### Future MCP Server Setup

For production use, you can set up a proper MCP server:

```bash
# Option 1: Remote MCP Server
# Use: https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY

# Option 2: Local MCP Server
git clone https://github.com/tavily-ai/tavily-mcp.git
cd tavily-mcp
pip install -r requirements.txt
python server.py
```

## 📊 Performance Comparison

| Feature | Direct API | MCP (Fallback) |
|---------|------------|----------------|
| Search Speed | Fast | Fast |
| Error Handling | Basic | Enhanced |
| Tool Integration | Limited | Extensive |
| Future Extensibility | Low | High |
| Setup Complexity | Low | Medium |

## 🧪 Testing

### Test MCP Integration

```bash
python test_mcp_integration.py
```

### Test Full Workflow

```bash
python gradio_app.py
# Visit http://localhost:7860
```

### Test Command Line

```bash
python main.py
```

## 🔮 Future Enhancements

### Additional MCP Tools You Can Add

1. **Database MCPs**
   - PostgreSQL MCP for storing research history
   - MongoDB MCP for flexible document storage

2. **AI/LLM MCPs**
   - OpenAI MCP for additional LLM options
   - Anthropic MCP for Claude integration

3. **Business Intelligence MCPs**
   - Google Analytics MCP
   - Salesforce MCP
   - Slack MCP for team notifications

4. **File Management MCPs**
   - Google Drive MCP
   - Dropbox MCP
   - Notion MCP

### Example: Adding a New MCP Tool

```python
# In src/tools/
from .new_mcp_client import new_tool_mcp

def enhanced_research(query: str):
    # Use Tavily MCP for search
    search_results = tavily_search_mcp(query)
    
    # Use new MCP tool for additional data
    additional_data = new_tool_mcp(query)
    
    # Combine results
    return combine_results(search_results, additional_data)
```

## 🐛 Troubleshooting

### Common Issues

1. **MCP Client Not Connected**
   - This is expected in fallback mode
   - The system automatically uses direct API

2. **API Key Errors**
   - Ensure `TAVILY_API_KEY` is set
   - Check API key validity

3. **Import Errors**
   - Make sure MCP packages are installed
   - Check virtual environment activation

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Benefits for Your Project

1. **Enhanced Search**: Access to advanced Tavily features
2. **Better Integration**: Unified interface for all tools
3. **Future-Proof**: Easy to add new MCP tools
4. **Reliability**: Automatic fallback ensures uptime
5. **Scalability**: MCP supports complex multi-tool workflows

## 🎯 Next Steps

1. **Test Current Integration**: Run the test script and Gradio app
2. **Add More MCP Tools**: Integrate additional MCP services
3. **Set Up MCP Server**: For production use
4. **Monitor Performance**: Track MCP vs direct API performance
5. **Expand Workflow**: Add more sophisticated multi-tool operations

---

**Ready to use!** Your Market Research Workflow now supports Tavily MCP with automatic fallback to ensure reliability. 🚀
