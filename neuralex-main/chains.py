from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts.chat import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder

def get_rag_chain(llm, vector_store, system_prompt, qa_prompt):
    # Retriever
    retriever = vector_store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": 10, "score_threshold": 0.3}
    )

    # QA Chain
    qa_prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", qa_prompt),
    ])
    question_answer_chain = StuffDocumentsChain(llm=llm, prompt=qa_prompt_template)

    # Conversational Retrieval Chain
    rag_chain = ConversationalRetrievalChain(
        retriever=retriever,
        combine_docs_chain=question_answer_chain,
        return_source_documents=True
    )

    return rag_chain
