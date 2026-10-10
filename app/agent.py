from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable
from app.config import get_settings

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]
    error: str | None = None
    retry_count: int
    model_used: str
    
    
class ProductionAgent:
    def __init__(self):
        settings = get_settings()
        self.primary_llm = ChatOpenAI(base_url=settings.deepseek_base_url,api_key=settings.deepseek_api_key,model = settings.primary_model, temperature= 0, timeout= 30)
        self.fallback_llm = ChatOpenAI(base_url=settings.deepseek_base_url,api_key=settings.deepseek_api_key,model = settings.primary_model, temperature= 0, timeout= 30)
        
        self.max_retries = settings.max_retries
        self.graph = self._build_graph()
        
    def _build_graph(self):
        """Build the LangGraph state machine"""
        
        def _process_message(state: AgentState) -> dict:
            """try to process the message with the primary model."""
            try: 
                reponsse = self.primary_llm.invoke(state["messages"])
                return {
                    "messages": [reponsse],
                    "error": None,
                    "model_used":"primary"
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count":state["retry_count"] + 1,
                    "model_used": ""
                }
        def _try_fallback(state: AgentState) -> dict:
            """fallback to secondary model"""
            try: 
                reponsse = self.fallback_llm.invoke(state["messages"])
                return {
                    "messages": [reponsse],
                    "error": None,
                    "model_used":"fallback"
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "model_used": ""
                }
        def _handle_error(state: AgentState) -> dict:
            """Return a graceful error message"""                        
            return {
                "messages":[
                    AIMessage(content="""
                              Sorry for this convinience, I'm having some troubles when processing your request, Please try again in a moment.
                              """)
                ],
                "model_used":"error_handler"
            }
        def _route_after_process(state: AgentState) -> str:
            """Decide what to do after primary model attempt."""
            if state.get("error") is None:
                return "done"
            if state["retry_count"] < self.max_retries:
                return "fallback"
            else:
                return "error"
            
        def _route_after_fall_fallback(state: AgentState) -> str:
            """Decide what to do after fallback attempt"""
            if state.get("error")  is None:
                return "Done"
            else: 
                return "error"
            
        graph = StateGraph(AgentState)
        
        graph.add_node("process", _process_message)
        graph.add_node("fallback",_try_fallback)
        graph.add_node("error",_handle_error)
        
        graph.add_edge(START,"process")
        graph.add_conditional_edges("process",_route_after_process,{"done":END,"fallback":"fallback","error":"error"})
        graph.add_conditional_edges("fallback",_route_after_fall_fallback,{"done":END, "error":"error"})
        graph.add_edge("error",END)
        
        return graph.compile()
    @traceable(name="production_agent_invoke")
    def invoke(self,message : str) -> dict:
        """Invoke to the Agent

        Args:
            message (str): User's message

        Returns:
            dict: {"response" : str, "model_used" : str, "error" : str | None}
        """
        result = self.graph.invoke({
            "messages" : [HumanMessage(content = message)],
            "error": None,
            "retry_count" : 0,
            "model_used": "",
        })
        return {
            "response" : result["messages"][-1].content,
            "model_used" : result.get("model_used","unknow"),
            "error": result.get("error")
        }