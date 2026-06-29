import os
from typing import TypedDict, List
from dotenv import load_dotenv

# Core LangChain & Groq Framework Modules
from langchain_groq import ChatGroq
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import PyPDFLoader

# LangGraph Engine Packages
from langgraph.graph import StateGraph, END

# 1. Boot up configurations
load_dotenv()

# Initialize Llama 3.3 for thinking/routing
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
web_search_tool = DuckDuckGoSearchRun()

print("Initializing local HuggingFace embedding framework...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Global variable tracker placeholder for graph access
retriever = None

# 2. Optimized Document Processor Function
def build_vector_context(file_path: str):
    """Slices documents using smart splits and initiates an MMR diversity retriever."""
    global retriever
    if not os.path.exists(file_path):
        print(f"File path '{file_path}' not found at boot. Waiting for UI uploads...")
        return None
        
    try:
        print(f"Loading and indexing {file_path}...")
        loader = PyPDFLoader(file_path)
        raw_pages = loader.load()
        
        # Split texts into smart 1000 character chunks with a 200 char overlap window
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        pages = text_splitter.split_documents(raw_pages)
        
        # Store text vectors into a local Chroma instance
        vector_store = Chroma.from_documents(pages, embeddings)
        
        # Deploy MMR (Maximum Marginal Relevance) to capture page 1 and avoid chunk dilution
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 20}
        )
        print("PDF successfully chunked and indexed into vector space!")
        return retriever
    except Exception as e:
        print(f"Parsing Failure: {str(e)}")
        return None

# Load initial file context pool if it exists at boot time
retriever = None



# 3. Define the Enhanced LangGraph State Backpack Schema
class AgentState(TypedDict):
    question: str
    chat_history: List[dict]  # List of past turns: [{"role": "user", "content": "..."}]
    current_source: str       # Tracks final selection: "history", "pdf", "web", or "none"
    context_data: str         # Holds extracted raw data snippets
    answer: str
    target_route: str         # Stores the orchestrator's chosen path selection


# 4. Define the Node Functions (The Graph Steps)

def classify_intent_router(state: AgentState):
    """GATEKEEPER NODE: Analyzes the question and explicitly decides which road to travel."""
    print("\n--- NODE: Classifying User Query Intent ---")
    question = state["question"]
    history = state["chat_history"]
    
    prompt = f"""You are the ultimate orchestrator for a multi-agent AI system. 
Your task is to classify where the answer to the user's question is most likely located.

USER QUESTION: '{question}'
PAST CHAT HISTORY CONTEXT: {history}

CLASSIFICATION RULES:
1. Choose 'pdf' if the query specifically references an uploaded document, manual, PDF context data, or asks about narrow details likely contained within an attached reference file.
2. Choose 'history' ONLY if the user is asking a direct follow-up, continuation, or clarification about what you *just* discussed in the immediate chat history log.
3. Choose 'web' if the query is about live news, general worldly knowledge, coding, or something completely unrelated to local documents.

Respond with exactly ONE word from these three options: pdf, history, or web. Do not write anything else.
"""
    response = llm.invoke(prompt)
    decision = response.content.strip().lower()
    
    # Safety string cleaning override guard
    if "pdf" in decision:
        decision = "pdf"
    elif "history" in decision:
        decision = "history"
    else:
        decision = "web"
        
    print(f"-> Orchestrator classified query intent road as: [{decision.upper()}]")
    return {"target_route": decision}


def check_chat_history(state: AgentState):
    """Step Lane A: Check if the question can be answered purely from past chat logs."""
    print("\n--- NODE: Checking Chat History ---")
    question = state["question"]
    history = state["chat_history"]
    
    if not history:
        return {"current_source": "none", "answer": ""}
        
    prompt = f"Based ONLY on this conversation history:\n{history}\n\nCan you answer this question: '{question}'? If yes, provide the detailed answer. If no, reply exactly with 'I DO NOT KNOW'."
    response = llm.invoke(prompt)
    
    if "I DO NOT KNOW" in response.content.upper():
        return {"current_source": "none", "answer": ""}
    
    return {"current_source": "history", "answer": response.content}


def query_pdf(state: AgentState):
    """Step Lane B: Query the vector database using strict prompt guards and physical page numbers."""
    print("\n--- NODE: Querying PDF (Enforcing Structural Page Numbers) ---")
    question = state["question"]
    
    if retriever is None:
        print("Retriever Reference Error: Database context has not been initialized.")
        return {"current_source": "none", "context_data": ""}
        
    try:
        # FIXED: Changed get_relevant_documents to the modern LangChain .invoke() framework method
        docs = retriever.invoke(question)
        
        formatted_context_list = []
        for d in docs:
            # Force the system to use the true physical page index integer from document properties (+1 for humans)
            true_file_page = d.metadata.get("page", 0) + 1  
            formatted_context_list.append(f": {true_file_page}\n{d.page_content}")
            
        pdf_context = "\n\n---\n\n".join(formatted_context_list)
        
        prompt = f"""You are a strict document index tracking engine. Your task is to tell the user where information is located.

PDF CONTENT CHUNKS:
{pdf_context}

USER QUESTION: '{question}'

INSTRUCTIONS:
1. Review the text chunks and provide an accurate answer.
2. CRITICAL CITATION RULE: You are strictly forbidden from reading or using page numbers written inside the raw sentences. You must ONLY look at the header tag '[METADATA_VERIFIED_PHYSICAL_PAGE: X]' above the text chunk to determine the page location.
3. List the verified page numbers clearly in your response.
4. If the chunks are completely irrelevant, reply exactly with: NOT IN PDF.
"""
        response = llm.invoke(prompt)
        
        if "NOT IN PDF" in response.content.strip().upper()[:20]:
            return {"current_source": "none", "context_data": ""}
            
        return {"current_source": "pdf", "answer": response.content, "context_data": pdf_context}
        
    except Exception as err:
        print(f"Retriever Execution Error: {str(err)}")
        return {"current_source": "none", "context_data": ""}


def query_web(state: AgentState):
    """Step Lane C: Fallback to the live internet search indexing pool."""
    print("\n--- NODE: Querying Live Web ---")
    question = state["question"]
    
    try:
        search_results = web_search_tool.run(question)
        prompt = f"Using these web search results:\n{search_results}\n\nProvide a comprehensive answer to: '{question}'"
        response = llm.invoke(prompt)
        return {"current_source": "web", "answer": response.content}
    except Exception as e:
        return {"current_source": "error", "answer": f"Failed to retrieve web data: {str(e)}"}


# 5. Define Conditional Routing Logic 

def route_initial_intent(state: AgentState):
    route = state.get("target_route", "web")
    if route == "history":
        return "history_lane"
    elif route == "pdf":
        return "pdf_lane"
    else:
        return "web_lane"

def route_after_history(state: AgentState):
    if state["current_source"] == "history":
        return "end"
    return "pdf"

def route_pdf_fallback(state: AgentState):
    if state["current_source"] == "pdf":
        return "end"
    print("-> Targeted PDF data content was silent. Swerving to secondary Live Web fallback...")
    return "web"


# 6. Build and Compile the Restructured State Machine
workflow = StateGraph(AgentState)

# Register nodes
workflow.add_node("intent_classifier", classify_intent_router)
workflow.add_node("check_history", check_chat_history)
workflow.add_node("query_pdf", query_pdf)
workflow.add_node("query_web", query_web)

# Set starting point
workflow.set_entry_point("intent_classifier")

# Map edge connections
workflow.add_conditional_edges(
    "intent_classifier",
    route_initial_intent,
    {
        "history_lane": "check_history",
        "pdf_lane": "query_pdf",
        "web_lane": "query_web"
    }
)
workflow.add_conditional_edges(
    "check_history",
    route_after_history,
    {
        "end": END,
        "pdf": "query_pdf"
    }
)
workflow.add_conditional_edges(
    "query_pdf",
    route_pdf_fallback,
    {
        "end": END,
        "web": "query_web"
    }
)
workflow.add_edge("query_web", END)

app = workflow.compile()
