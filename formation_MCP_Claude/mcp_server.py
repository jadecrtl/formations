from mcp.server.fastmcp import FastMCP
from pydantic import Field
from mcp.server.fastmcp.prompts import base

# ------------------------------------------------------------------------------
# 1. INITIALISATION DU SERVEUR FASTMCP
# ------------------------------------------------------------------------------
# FastMCP simplifie la creation d'un serveur MCP en utilisant des decorateurs (@mcp.tool, etc.).
# log_level="ERROR" evite de polluer le flux standard (stdio) avec des logs de debug.
mcp = FastMCP("DocumentMCP", log_level="ERROR")

# Simule une source de donnees / base de documents en memoire (fictive)
docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}


# ------------------------------------------------------------------------------
# 2. LES OUTILS (TOOLS)
# ------------------------------------------------------------------------------
# REGLE DU QUIZ : Les outils sont controles par le MODeLE (LLM). 
# C'est Claude qui decide de les appeler quand une requete utilisateur l'exige.
# Les descriptions fournies a FastMCP et les 'Field(description=...)' sont transmises 
# a Claude dans son schema JSON pour qu'il sache quand et comment les utiliser.

@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    # Pydantic Field permet d'expliquer au LLM ce que represente ce parametre
    doc_id: str = Field(description="Id of the document to read"),
):
    """Permet au LLM de lire le texte contenu dans l'un des documents."""
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    return docs[doc_id]


@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string",
)
def edit_document(
    doc_id: str = Field(description="Id of the document that will be edited"),
    old_str: str = Field(
        description="The text to replace. Must match exactly, including whitespace"
    ),
    new_str: str = Field(
        description="The new text to insert in place of the old text"
    ),
):
    """Permet au LLM de modifier le texte d'un document existant."""
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    # Remplace old_str par new_str directement dans le dictionnaire
    docs[doc_id] = docs[doc_id].replace(old_str, new_str)


# ------------------------------------------------------------------------------
# 3. LES RESSOURCES (RESOURCES)
# ------------------------------------------------------------------------------
# REGLE DU QUIZ : Les ressources sont controlees par l'UTILISATEUR ou l'APPLICATION (Client).
# Elles se comportent comme des URLs (docs://...) et exposent des donnees passives.
# C'est ce qui s'active quand on tape '@deposition.md' dans le chat.

# Ressource statique/statique : liste les identifiants disponibles (format JSON)
@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    """Retourne la liste de toutes les cles (IDs) de documents disponibles."""
    return list(docs.keys())


# Ressource dynamique/modelisee avec parametre d'URI {doc_id} (format texte brut)
@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")
def fetch_doc(doc_id: str) -> str:
    """Retourne le contenu brut du document demande par son URI."""
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")
    return docs[doc_id]


# ------------------------------------------------------------------------------
# 4. LES PROMPTS
# ------------------------------------------------------------------------------
# REGLE DU QUIZ : Les prompts sont des modeles interactifs pour l'UTILISATEUR.
# Ils pre-parametrent une tache pour le LLM.
# Declenches dans l'interface par un slash command (ex: /format deposition.md).

@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format.",
)
def format_document(
    doc_id: str = Field(description="Id of the document to format"),
) -> list[base.Message]:
    """Prepare les instructions pour demander au LLM de reformat en Markdown."""
    prompt = f"""
    Your goal is to reformat a document to be written with markdown syntax.

    The id of the document you need to reformat is:
    <document_id>
    {doc_id}
    </document_id>

    Add in headers, bullet points, tables, etc as necessary. Feel free to add in extra text, but don't change the meaning of the report.
    Use the 'edit_document' tool to edit the document. After the document has been edited, respond with the final version of the doc. Don't explain your changes.
    """

    # Retourne une liste de messages de type UserMessage avec le prompt pret a l'emploi
    return [base.UserMessage(prompt)]


# ------------------------------------------------------------------------------
# 5. DEMARRAGE DU SERVEUR
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # transport="stdio" : Le serveur communique avec le client via l'entree/sortie standard
    # (stdin / stdout), ce qui est le mode standard pour les serveurs locaux en MCP.
    mcp.run(transport="stdio")