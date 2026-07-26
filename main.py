import hashlib
from typing import Any, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response


app = FastAPI(title="IITM Live MCP Server")


# Your registered IITM exam email.
# It must be trimmed and lowercase.
NORMALIZED_EMAIL = "22f3000236@ds.study.iitm.ac.in"

SERVER_NAME = "iitm-solve-challenge-server"
SERVER_VERSION = "1.0.0"


def jsonrpc_result(request_id: Any, result: Any) -> JSONResponse:
    """Create a standard JSON-RPC success response."""
    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
    )


def jsonrpc_error(
    request_id: Any,
    code: int,
    message: str,
) -> JSONResponse:
    """Create a standard JSON-RPC error response."""
    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
    )


def solve_exam_challenge(challenge: str) -> str:
    """
    Return the first 16 lowercase hexadecimal characters of:

        SHA-256("{challenge}:{normalizedEmail}")
    """

    source_text = f"{challenge}:{NORMALIZED_EMAIL}"

    return hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()[:16]


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "MCP server is running",
        "mcp_endpoint": "/mcp",
    }


@app.get("/mcp")
def mcp_information() -> dict[str, str]:
    """
    A simple browser-friendly response.

    Actual MCP protocol communication happens through POST /mcp.
    """
    return {
        "message": "This is an MCP Streamable HTTP endpoint.",
        "method": "Use POST requests for MCP messages.",
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    x_exam_challenge: Optional[str] = Header(
        default=None,
        alias="X-Exam-Challenge",
    ),
    x_exam_timestamp: Optional[str] = Header(
        default=None,
        alias="X-Exam-Timestamp",
    ),
    x_exam_signature: Optional[str] = Header(
        default=None,
        alias="X-Exam-Signature",
    ),
):
    """
    Handle the small MCP protocol surface required by the grader.

    Supported methods:
    - initialize
    - notifications/initialized
    - tools/list
    - tools/call
    """

    try:
        body = await request.json()
    except Exception:
        return jsonrpc_error(
            request_id=None,
            code=-32700,
            message="Parse error",
        )

    if not isinstance(body, dict):
        return jsonrpc_error(
            request_id=None,
            code=-32600,
            message="Invalid Request",
        )

    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    # ---------------------------------------------------------
    # 1. MCP initialization handshake
    # ---------------------------------------------------------
    if method == "initialize":
        requested_protocol_version = params.get(
            "protocolVersion",
            "2025-03-26",
        )

        return jsonrpc_result(
            request_id,
            {
                "protocolVersion": requested_protocol_version,
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        )

    # ---------------------------------------------------------
    # 2. Client initialization notification
    # ---------------------------------------------------------
    if method == "notifications/initialized":
        # JSON-RPC notifications have no response body.
        return Response(status_code=202)

    # ---------------------------------------------------------
    # 3. Return the one required tool
    # ---------------------------------------------------------
    if method == "tools/list":
        return jsonrpc_result(
            request_id,
            {
                "tools": [
                    {
                        "name": "solve_challenge",
                        "description": (
                            "Returns the exam challenge digest using "
                            "the X-Exam-Challenge HTTP request header."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )

    # ---------------------------------------------------------
    # 4. Execute solve_challenge
    # ---------------------------------------------------------
    if method == "tools/call":
        tool_name = params.get("name")

        if tool_name != "solve_challenge":
            return jsonrpc_error(
                request_id=request_id,
                code=-32602,
                message="Unknown tool",
            )

        # The challenge must come from the HTTP header,
        # not from the JSON request body.
        if not x_exam_challenge:
            return jsonrpc_result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "Missing X-Exam-Challenge header",
                        }
                    ],
                    "isError": True,
                },
            )

        answer = solve_exam_challenge(x_exam_challenge)

        return jsonrpc_result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": answer,
                    }
                ],
                "isError": False,
            },
        )

    # ---------------------------------------------------------
    # Optional ping support
    # ---------------------------------------------------------
    if method == "ping":
        return jsonrpc_result(
            request_id,
            {},
        )

    return jsonrpc_error(
        request_id=request_id,
        code=-32601,
        message=f"Method not found: {method}",
    )