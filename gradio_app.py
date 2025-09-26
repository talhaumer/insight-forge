#!/usr/bin/env python3
"""
Gradio Web Interface for Market Research Workflow
Simple web app for users to input queries and get research reports
"""

import gradio as gr
import sys
import os
import json
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our workflow components
from src.graph import run_market_research
from src.observability import metrics_collector, generate_metrics_summary

def generate_research_report(query):
    """Generate a research report for the given query"""
    if not query or not query.strip():
        return "Please enter a valid research query.", None, None
    
    try:
        # Run the market research workflow
        result = run_market_research(query.strip())
        
        # Format the report for display
        if 'topic' in result and 'summary' in result:
            # Format the main report
            report_text = f"""
# {result.get('topic', 'Research Report')}

## Summary
{result.get('summary', 'No summary available')}

## Key Facts
"""
            
            # Add facts
            if 'facts' in result and result['facts']:
                for i, fact in enumerate(result['facts'], 1):
                    report_text += f"\n{i}. **{fact.get('fact', 'N/A')}**\n"
                    report_text += f"   - Source: {fact.get('source', 'N/A')}\n"
                    report_text += f"   - Confidence: {fact.get('confidence', 'N/A')}\n"
            
            # Add references
            if 'references' in result and result['references']:
                report_text += f"\n## References\n"
                for i, ref in enumerate(result['references'], 1):
                    report_text += f"{i}. {ref}\n"
            
            report_text += f"\n---\n*Generated: {result.get('timestamp', 'N/A')}*"
            
            # Get metrics for the sidebar
            metrics = metrics_collector.get_metrics()
            metrics_text = generate_metrics_summary(metrics)
            
            # Create a simple JSON summary for download - save to file
            json_summary = {
                "query": query,
                "topic": result.get('topic', ''),
                "summary": result.get('summary', ''),
                "facts_count": len(result.get('facts', [])),
                "references_count": len(result.get('references', [])),
                "timestamp": result.get('timestamp', ''),
                "facts": result.get('facts', []),
                "references": result.get('references', [])
            }
            
            # Save JSON to a temporary file
            import tempfile
            import os
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(json_summary, temp_file, indent=2)
            temp_file.close()
            
            return report_text, metrics_text, temp_file.name
        else:
            return "Error: Could not generate report. Please try again.", None, None
            
    except Exception as e:
        error_msg = f"Error generating report: {str(e)}"
        return error_msg, None, None

def create_gradio_interface():
    """Create the Gradio interface"""
    
    with gr.Blocks(
        title="Market Research Workflow",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        .report-box {
            background-color: #f8f9fa !important;
            border: 1px solid #dee2e6 !important;
            border-radius: 8px !important;
            padding: 20px !important;
            margin: 10px 0 !important;
            color: #212529 !important;
        }
        .report-box h1, .report-box h2, .report-box h3 {
            color: #212529 !important;
        }
        .report-box p, .report-box li {
            color: #212529 !important;
        }
        .report-box strong {
            color: #0d6efd !important;
        }
        .metrics-box {
            background-color: #e7f3ff !important;
            border: 1px solid #b3d9ff !important;
            border-radius: 8px !important;
            padding: 15px !important;
            margin: 10px 0 !important;
            color: #212529 !important;
        }
        .metrics-box h1, .metrics-box h2, .metrics-box h3 {
            color: #212529 !important;
        }
        .metrics-box p, .metrics-box li {
            color: #212529 !important;
        }
        .gradio-markdown {
            color: #212529 !important;
        }
        .gradio-markdown h1, .gradio-markdown h2, .gradio-markdown h3 {
            color: #212529 !important;
        }
        .gradio-markdown p, .gradio-markdown li {
            color: #212529 !important;
        }
        .gradio-markdown strong {
            color: #0d6efd !important;
        }
        """
    ) as demo:
        
        gr.Markdown("""
        # 🔍 Market Research Workflow
        
        Enter a research query below to generate a comprehensive market research report using our multi-agent AI system.
        
        **Features:**
        - Real-time web search with Tavily
        - AI-powered analysis with Groq LLM
        - Multi-agent workflow (Researcher, Analyst, Writer, Reviewer)
        - Security guardrails and content validation
        - Comprehensive metrics and tracing
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                # Input section
                query_input = gr.Textbox(
                    label="Research Query",
                    placeholder="Enter your market research question (e.g., 'AI market trends 2025', 'Electric vehicle adoption rates')",
                    lines=2,
                    max_lines=4
                )
                
                submit_btn = gr.Button("🔍 Generate Report", variant="primary", size="lg")
                
                # Output section
                report_output = gr.Markdown(
                    label="Research Report",
                    value="Enter a query above to generate a research report...",
                    elem_classes=["report-box"]
                )
                
                # Download button
                download_btn = gr.DownloadButton(
                    label="📥 Download Report (JSON)",
                    visible=False
                )
                
            with gr.Column(scale=1):
                # Metrics sidebar
                metrics_output = gr.Markdown(
                    label="System Metrics",
                    value="Metrics will appear here after generating a report...",
                    elem_classes=["metrics-box"]
                )
        
        # Examples section
        gr.Markdown("### 💡 Example Queries")
        examples = gr.Examples(
            examples=[
                "Electric vehicle market trends 2025",
                "AI market growth predictions",
                "Sustainable energy investments",
                "Remote work technology trends",
                "Cybersecurity market analysis",
                "Healthcare AI adoption rates"
            ],
            inputs=query_input,
            label="Click on an example to try it"
        )
        
        # Event handlers
        def handle_submit(query):
            report, metrics, json_file_path = generate_research_report(query)
            return (
                report,
                metrics,
                gr.update(visible=True, value=json_file_path),
                gr.update(value=json_file_path)
            )
        
        submit_btn.click(
            fn=handle_submit,
            inputs=query_input,
            outputs=[report_output, metrics_output, download_btn, download_btn]
        )
        
        # Also trigger on Enter key
        query_input.submit(
            fn=handle_submit,
            inputs=query_input,
            outputs=[report_output, metrics_output, download_btn, download_btn]
        )
        
        # Footer
        gr.Markdown("""
        ---
        **Powered by:** LangGraph + Groq LLM + Tavily Search + LangSmith Tracing
        
        This system uses a multi-agent architecture with comprehensive security guardrails, 
        real-time web search, and AI-powered analysis to generate market research reports.
        """)
    
    return demo

if __name__ == "__main__":
    # Create and launch the interface
    demo = create_gradio_interface()
    
    print("🚀 Starting Market Research Workflow Web Interface...")
    print("📊 Features: Multi-agent AI, Real-time search, Security guardrails")
    print("🌐 The interface will open in your browser")
    
    demo.launch(
        server_name="0.0.0.0",  # Allow external access
        server_port=7860,       # Default Gradio port
        share=False,            # Set to True to create a public link
        show_error=True,        # Show errors in the interface
        quiet=False             # Show startup messages
    )
