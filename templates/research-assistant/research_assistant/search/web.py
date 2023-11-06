import json

from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableMap
from langchain.schema.messages import SystemMessage
from datetime import datetime
from langchain.utilities import DuckDuckGoSearchAPIWrapper
import requests
from bs4 import BeautifulSoup

ddg_search = DuckDuckGoSearchAPIWrapper()







def scrape_text(url: str):
    # Send a GET request to the webpage
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the content of the request with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract all text from the webpage
        page_text = soup.get_text(separator=' ', strip=True)

        # Print the extracted text
        return page_text
    else:
        return  f"Failed to retrieve the webpage: Status code {response.status_code}"

def web_search(query:str , num_results: int):
    results = ddg_search.results(query, num_results)
    return [r['link'] for r in results]

def generate_search_queries_prompt(question):
    """ Generates the search queries prompt for the given question.
    Args: question (str): The question to generate the search queries prompt for
    Returns: str: The search queries prompt for the given question
    """

    return f'Write 3 google search queries to search online that form an objective opinion from the following: "{question}"'\
           f'You must respond with a list of strings in the following format: ["query 1", "query 2", "query 3"].'


search_message = (generate_search_queries_prompt("{question}"))
SEARCH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{agent_prompt}"),
    ("user", search_message)
])

AUTO_AGENT_INSTRUCTIONS =  """
This task involves researching a given topic, regardless of its complexity or the availability of a definitive answer. The research is conducted by a specific agent, defined by its type and role, with each agent requiring distinct instructions.
Agent
The agent is determined by the field of the topic and the specific name of the agent that could be utilized to research the topic provided. Agents are categorized by their area of expertise, and each agent type is associated with a corresponding emoji.

examples:
task: "should I invest in apple stocks?"
response: 
{
    "agent": "💰 Finance Agent",
    "agent_role_prompt: "You are a seasoned finance analyst AI assistant. Your primary goal is to compose comprehensive, astute, impartial, and methodically arranged financial reports based on provided data and trends."
}
task: "could reselling sneakers become profitable?"
response: 
{ 
    "agent":  "📈 Business Analyst Agent",
    "agent_role_prompt": "You are an experienced AI business analyst assistant. Your main objective is to produce comprehensive, insightful, impartial, and systematically structured business reports based on provided business data, market trends, and strategic analysis."
}
task: "what are the most interesting sites in Tel Aviv?"
response:
{
    "agent:  "🌍 Travel Agent",
    "agent_role_prompt": "You are a world-travelled AI tour guide assistant. Your main purpose is to draft engaging, insightful, unbiased, and well-structured travel reports on given locations, including history, attractions, and cultural insights."
}
"""
CHOOSE_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=AUTO_AGENT_INSTRUCTIONS),
    ("user", "task: {task}")
])

SUMMARY_TEMPLATE = """{text} 

-----------

Using the above text, answer in short the following question: 

> {question}
 
-----------
if the question cannot be answered using the text, imply summarize the text. Include all factual information, numbers, stats etc if available."""
SUMMARY_PROMPT = ChatPromptTemplate.from_template(SUMMARY_TEMPLATE)

scrape_and_summarize = {
    "question": lambda x: x["question"],
    "text": lambda x: scrape_text(x['url'])[:10000],
    "url": lambda x: x['url']
} | RunnableMap({
        "summary": SUMMARY_PROMPT | ChatOpenAI(temperature=0) | StrOutputParser(),
        "url": lambda x: x['url']
}) | (lambda x: f"Source Url: {x['url']}\nSummary: {x['summary']}")

multi_search = (
    lambda x: [
        {"url": url, "question": x["question"]}
        for url in web_search(query=x["question"], num_results=3)
   ]
) | scrape_and_summarize.map() | (lambda x: "\n".join(x))

search_query = SEARCH_PROMPT | ChatOpenAI(temperature=0) | StrOutputParser() | json.loads
choose_agent = CHOOSE_AGENT_PROMPT | ChatOpenAI(temperature=0) | StrOutputParser() | json.loads

get_search_queries = {
    "question": lambda x: x,
    "agent_prompt": {"task": lambda x: x} | choose_agent | (lambda x: x["agent_role_prompt"])
} | search_query


chain = (
    get_search_queries
    | (lambda x: [{"question": q} for q in x])
    | multi_search.map()
    | (lambda x: "\n\n".join(x))
)
