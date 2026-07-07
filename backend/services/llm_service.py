"""
LLM Service — Claude API / DeepSeek API integration with tool calling.
Embeds AI intelligence into the building energy analysis web app.
"""
import sys, os, json, uuid
from typing import AsyncGenerator, Dict, Any, List, Optional
from datetime import datetime

# Read SKILL.md for system prompt + import skill scripts
from config import SKILL_SCRIPTS_DIR, SKILL_MD_PATH
if SKILL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS_DIR)

from config import ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LLM_PROVIDER, UPLOAD_DIR

# ============================================================
# System Prompt
# ============================================================

def load_system_prompt() -> str:
    """Load SKILL.md and add tool usage instructions."""
    base_prompt = ""
    if os.path.exists(SKILL_MD_PATH):
        with open(SKILL_MD_PATH, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
    else:
        base_prompt = "你是一个建筑能耗分析专家助手。"

    tool_instructions = """

## 网站工具模式

你现在运行在一个建筑能耗分析网站上。用户通过聊天界面上传 Excel/CSV 文件并和你对话。

### ⚠️ 强制工作流程（必须严格遵守）

**当用户上传文件并要求分析时，按以下顺序执行，不可跳过：**

**第1步：先调用 `preview_excel_file` 查看文件结构**
    - 必须传入 file_id
    - 仔细查看返回的每个 Sheet 的名称、行列数、前几行数据
    - 判断数据格式：
      a) 标准格式：第1列为"月份"或数字1-12，后续列标题含"电""气"等 → 用 parse_excel_auto
      b) 转置格式：第1列为建筑名/子项名，后续列为逐月数据 → 用 parse_transposed_sum
      c) 复杂格式：需要自己推断列映射 → 用 parse_excel_auto 并指定 column_map

**第2步：解析数据**
    - 标准格式：调用 parse_excel_auto，必须传入正确的 column_map（列号用数字）
    - 转置格式：调用 parse_transposed_sum，传入正确的 start_row 和 month_start_col
    - 不要猜测参数！参数错误会导致解析失败

**第3步：询问用户确认信息**
    - 如果用户没提供：建筑面积、建筑类型、所在地区 → 主动问
    - 建筑类型：办公/商业/酒店/学校/医院/住宅
    - 所在地区：必须包含省份（和城市，如江苏省苏州市）

**第4步：运行完整分析**
    - 调用 run_full_analysis，传入解析好的 energy_data 和 building_info
    - 务必填全 building_info 的 name、area、type、location、year

**第5步：展示结果并询问是否生成报告**
    - 用简洁格式展示：总能耗(tce)、单位面积能耗、碳排放、对标结果
    - 主动问："需要生成 Word 报告吗？"

### 列号格式说明
- parse_excel_auto 的 column_map 值必须是数字（如 "5" 表示第E列，"2" 表示第B列）
- A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8, ...

### 重要规则
- 用中文回复，专业但不啰嗦
- 每次只做一个操作，完成后等用户确认再做下一步
- 如果工具调用失败，仔细看错误信息并调整参数重试
- 文件ID可能很长（UUID格式），完整使用不要截断
"""
    return base_prompt.strip() + tool_instructions.strip()


# ============================================================
# Tool Definitions
# ============================================================

TOOLS = [
    {
        "name": "preview_excel_file",
        "description": "预览上传的 Excel 文件结构。查看有哪些 Sheet、每一列的名称、前几行数据。在解析前必须调用此工具了解文件结构。",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "上传文件的 ID"},
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "parse_excel_auto",
        "description": "标准格式解析：每行=一个月，列=能源类型。传入 sheet 名和列映射（如 electricity_kwh→E列），自动识别并解析。",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "上传文件的 ID"},
                "sheet_name": {"type": "string", "description": "工作表名称（可选，默认自动选择）"},
                "column_map": {
                    "type": "object",
                    "description": "列映射。key=能源类型(electricity_kwh/gas_m3/heat_gj)，value=Excel列字母如'E'或列号如'5'",
                    "properties": {
                        "electricity_kwh": {"type": "string", "description": "电力列号，如E或5"},
                        "gas_m3": {"type": "string", "description": "燃气列号，如G或7"},
                        "heat_gj": {"type": "string", "description": "热力列号，如H或8"},
                    },
                },
            },
            "required": ["file_id", "column_map"],
        },
    },
    {
        "name": "parse_transposed_sum",
        "description": "转置格式解析：每行=一个建筑/子项，每列=一个月。自动汇总所有行的月度数据得到建筑总能耗。",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "上传文件的 ID"},
                "sheet_name": {"type": "string", "description": "工作表名称（可选，默认自动选择含用能/用电关键词的sheet）"},
                "start_row": {"type": "integer", "description": "数据起始行号（1-based，含表头的下一行），默认2"},
                "month_start_col": {"type": "integer", "description": "第一个月份所在列号（1-based），默认2"},
                "num_months": {"type": "integer", "description": "月份列数，默认12"},
                "year": {"type": "integer", "description": "数据年份，如2024"},
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "run_full_analysis",
        "description": "执行完整能耗分析：能源比例、逐月趋势、单位面积强度、碳排放、标准对标。需要先解析数据获得 energy_data。",
        "input_schema": {
            "type": "object",
            "properties": {
                "energy_data": {
                    "type": "array",
                    "description": "月度能耗数据数组，每项含 month, electricity_kwh, gas_m3, heat_gj",
                    "items": {"type": "object"},
                },
                "building_info": {
                    "type": "object",
                    "description": "建筑信息",
                    "properties": {
                        "name": {"type": "string", "description": "建筑名称"},
                        "area": {"type": "number", "description": "建筑面积(m²)"},
                        "type": {"type": "string", "description": "建筑类型：办公/商业/酒店/学校/医院/住宅"},
                        "location": {"type": "string", "description": "所在省份+城市，如江苏省苏州市"},
                        "year": {"type": "integer", "description": "数据年份"},
                    },
                    "required": ["name", "area", "type", "location"],
                },
                "coal_factors_preset": {"type": "string", "description": "折算系数预设：default|national|jiangsu_hotel|db31_783|db31_552|db31_1341，不确定时空着"},
            },
            "required": ["energy_data", "building_info"],
        },
    },
    {
        "name": "generate_word_report",
        "description": "生成 Word (.docx) 格式的能耗分析报告，返回下载链接。",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_json": {"type": "object", "description": "完整分析结果JSON（来自 run_full_analysis 的返回值）"},
            },
            "required": ["analysis_json"],
        },
    },
]


# ============================================================
# Tool Executor
# ============================================================

def _find_file(file_id: str) -> str:
    """Find uploaded file path by ID prefix."""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            return os.path.join(UPLOAD_DIR, fname)
    return ""


def _col_letter_to_number(col_ref: str) -> int:
    """Convert Excel column letter(s) to 1-based index. 'A'→1, 'E'→5, 'AA'→27."""
    col_ref = str(col_ref).upper().strip()
    if col_ref.isdigit():
        return int(col_ref)
    result = 0
    for char in col_ref:
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result


def execute_tool(tool_name: str, tool_args: dict) -> dict:
    """Execute a tool by name and return the result dict."""
    try:
        if tool_name == "preview_excel_file":
            from services.parse_service import get_file_preview
            preview = get_file_preview(tool_args["file_id"], max_rows=8)
            # Simplify for LLM consumption
            simplified = {
                "file_id": tool_args["file_id"],
                "sheet_count": len(preview.get("sheets", [])),
                "detection": preview.get("detection", {}),
                "sheets": [],
            }
            for sheet in preview.get("sheets", []):
                s = {
                    "name": sheet["name"],
                    "rows": sheet["total_rows"],
                    "cols": sheet["total_cols"],
                    "headers_row1": sheet.get("headers", {}),
                    "sample_rows": [],
                }
                for row_data in sheet.get("preview_rows", [])[:5]:
                    s["sample_rows"].append({
                        "row": row_data["row"],
                        "values": row_data.get("cells", {}),
                    })
                simplified["sheets"].append(s)
            return {"success": True, "data": simplified}

        elif tool_name == "parse_excel_auto":
            from services.parse_service import parse_file
            column_map = {}
            raw_map = tool_args.get("column_map", {})
            for ctype, col_ref in raw_map.items():
                column_map[ctype] = str(_col_letter_to_number(col_ref))

            result = parse_file(
                tool_args["file_id"],
                column_map=column_map if column_map else None,
                daily=False,
            )
            if result.get("error"):
                return {"success": False, "error": result["error"], "data": result}
            energy = result.get("energy_data", [])
            total_kwh = sum(r.get("electricity_kwh", 0) or 0 for r in energy)
            total_gas = sum(r.get("gas_m3", 0) or 0 for r in energy)
            return {
                "success": True,
                "data": {
                    "energy_data": energy,
                    "building_info": result.get("building_info", {}),
                    "months": len(energy),
                    "total_kwh": round(total_kwh, 0),
                    "total_gas_m3": round(total_gas, 0),
                }
            }

        elif tool_name == "parse_transposed_sum":
            from services.parse_service import parse_file_transposed
            result = parse_file_transposed(
                file_id=tool_args["file_id"],
                sheet_name=tool_args.get("sheet_name"),
                start_row=tool_args.get("start_row", 2),
                month_start_col=tool_args.get("month_start_col", 2),
                num_months=tool_args.get("num_months", 12),
                year=tool_args.get("year", datetime.now().year),
            )
            if result.get("error"):
                return {"success": False, "error": result["error"], "data": result}
            energy = result.get("energy_data", [])
            total_kwh = sum(r.get("electricity_kwh", 0) or 0 for r in energy)
            return {
                "success": True,
                "data": {
                    "energy_data": energy,
                    "building_info": result.get("building_info", {}),
                    "months": len(energy),
                    "total_kwh": round(total_kwh, 0),
                    "meta": result.get("meta", {}),
                }
            }

        elif tool_name == "run_full_analysis":
            from services.energy_service import run_analysis
            from services.carbon_service import run_carbon_analysis

            energy_data = tool_args["energy_data"]
            building_info = tool_args["building_info"]
            area = building_info.get("area", 0)
            province = building_info.get("location", "")
            btype = building_info.get("type", "")
            preset = tool_args.get("coal_factors_preset", "")

            # Run energy analysis
            analysis = run_analysis(energy_data, building_info, coal_factors_preset=preset or "default")

            # Run carbon analysis + standard benchmark
            carbon = run_carbon_analysis(
                energy_data=energy_data,
                building_info=building_info,
                province=province,
                building_type=btype,
            )

            # Extract key results
            total_coal = carbon.get("total_coal_kgce", 0)
            coal_per_m2 = carbon.get("coal_per_m2_kgce", 0)
            carbon_total = carbon.get("total_emission_tons", 0)
            carbon_per_m2_val = carbon.get("carbon_intensity_kgco2_per_m2", 0)
            sc = carbon.get("standard_comparison", {})

            return {
                "success": True,
                "data": {
                    "total_coal_kgce": total_coal,
                    "total_coal_tce": round(total_coal / 1000, 1),
                    "coal_per_m2_kgce": coal_per_m2,
                    "total_emission_tons": carbon_total,
                    "carbon_intensity_kgco2_per_m2": carbon_per_m2_val,
                    "standard_comparison": {
                        "standard": sc.get("standard_source", ""),
                        "level": sc.get("level", ""),
                        "icon": sc.get("icon", ""),
                        "message": sc.get("message", ""),
                        "energy_message": sc.get("energy_message", ""),
                        "carbon_message": sc.get("carbon_message", ""),
                        "suggestion": sc.get("suggestion", ""),
                    },
                    "full_result": {**analysis, **carbon},
                }
            }

        elif tool_name == "generate_word_report":
            from services.report_service import generate_word_report

            analysis_json = tool_args["analysis_json"]
            full = analysis_json.get("full_result", analysis_json)

            data = {
                "building_info": full.get("building_info", {}),
                "energy_proportion": full.get("energy_proportion", {}),
                "monthly_trend": full.get("monthly_trend", {}),
                "carbon_emission": {
                    "total_emission_tons": full.get("total_emission_tons", 0),
                    "emission_breakdown": full.get("emission_breakdown", {}),
                    "monthly_emission": full.get("monthly_emission", []),
                    "grid_factor_used": full.get("grid_factor_used", 0),
                    "region": full.get("region", ""),
                },
                "standard_comparison": full.get("standard_comparison", {}),
                "coal_per_m2_kgce": full.get("coal_per_m2_kgce", 0),
                "carbon_intensity_kgco2_per_m2": full.get("carbon_intensity_kgco2_per_m2", 0),
            }
            output_path, output_filename = generate_word_report(data)
            return {
                "success": True,
                "data": {
                    "filename": output_filename,
                    "download_url": f"/api/report/download/{output_filename}",
                    "message": f"报告已生成: {output_filename}",
                }
            }

        else:
            return {"success": False, "error": f"未知工具: {tool_name}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ============================================================
# Chat Session Management (in-memory)
# ============================================================

_sessions: Dict[str, List[dict]] = {}  # session_id -> messages


def get_or_create_session(session_id: str = None) -> str:
    """Get existing or create new chat session."""
    if session_id and session_id in _sessions:
        return session_id
    new_id = session_id or str(uuid.uuid4())[:8]
    if new_id not in _sessions:
        _sessions[new_id] = []
    return new_id


def get_session_history(session_id: str) -> list:
    return _sessions.get(session_id, [])


def clear_session(session_id: str):
    if session_id in _sessions:
        _sessions[session_id] = []


# ============================================================
# Streaming Chat (using anthropic SDK)
# ============================================================

async def chat_stream(
    session_id: str,
    message: str,
    file_id: str = None,
    file_preview: dict = None,
) -> AsyncGenerator[str, None]:
    """
    Stream chat responses via SSE.
    Dispatches to Anthropic or DeepSeek based on LLM_PROVIDER config.
    """
    if LLM_PROVIDER == 'deepseek':
        async for event in _chat_stream_deepseek(session_id, message, file_id, file_preview):
            yield event
    else:
        async for event in _chat_stream_anthropic(session_id, message, file_id, file_preview):
            yield event


async def _chat_stream_anthropic(
    session_id: str, message: str, file_id: str = None, file_preview: dict = None,
) -> AsyncGenerator[str, None]:
    """Claude API via Anthropic SDK."""
    import anthropic

    if not ANTHROPIC_API_KEY:
        yield _sse_event("error", {"message": "未配置 ANTHROPIC_API_KEY"})
        return

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # Build messages
    session = _sessions.setdefault(session_id, [])

    # Add file context to user message
    user_content = []
    if file_id or file_preview:
        user_content.append({"type": "text", "text": message or "请查看这个文件的结构"})
        ctx_parts = []
        if file_id:
            ctx_parts.append(f"已上传文件ID: {file_id}")
            # Try to find file
            fpath = _find_file(file_id)
            if fpath:
                ctx_parts.append(f"文件名: {os.path.basename(fpath)}")
                ctx_parts.append(f"文件大小: {os.path.getsize(fpath)} bytes")
        if file_preview:
            ctx_parts.append(f"文件预览: {json.dumps(file_preview, ensure_ascii=False, indent=2)}")
        if ctx_parts:
            user_content.append({"type": "text", "text": "\n".join(ctx_parts)})
    else:
        user_content.append({"type": "text", "text": message})

    session.append({"role": "user", "content": user_content})

    # Build messages for API
    api_messages = []
    for msg in session:
        content = msg["content"]
        if isinstance(content, list):
            # Extract text parts
            text_parts = [p["text"] for p in content if p.get("type") == "text"]
            api_messages.append({"role": msg["role"], "content": "\n".join(text_parts)})
        else:
            api_messages.append({"role": msg["role"], "content": str(content)})

    system_prompt = load_system_prompt()

    # Tool calling loop
    max_turns = 5
    turn = 0
    full_response = ""

    while turn < max_turns:
        turn += 1
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=api_messages,
                tools=TOOLS,
            )
        except Exception as e:
            yield _sse_event("error", {"message": f"Claude API 错误: {str(e)}"})
            return

        # Process response
        has_tool_calls = False
        for block in response.content:
            if block.type == "text":
                text = block.text
                full_response += text
                yield _sse_event("text", {"text": text})

            elif block.type == "tool_use":
                has_tool_calls = True
                tool_name = block.name
                tool_args = block.input if isinstance(block.input, dict) else {}

                yield _sse_event("tool_call", {"tool": tool_name, "args": tool_args})

                # Execute tool
                result = execute_tool(tool_name, tool_args)
                yield _sse_event("tool_result", {"tool": tool_name, "success": result.get("success"), "summary": _summarize_result(tool_name, result)})

                # Add to messages
                api_messages.append({
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": block.id, "name": tool_name, "input": tool_args}],
                })
                api_messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)}],
                })

        if not has_tool_calls:
            break

    # Save assistant response
    if full_response:
        session.append({"role": "assistant", "content": full_response})

    yield _sse_event("done", {})


# ---- DeepSeek (OpenAI-compatible) tool format ----

def _to_openai_tools() -> list:
    """Convert Anthropic-format TOOLS to OpenAI function calling format."""
    openai_tools = []
    for t in TOOLS:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return openai_tools


async def _chat_stream_deepseek(
    session_id: str, message: str, file_id: str = None, file_preview: dict = None,
) -> AsyncGenerator[str, None]:
    """DeepSeek API via OpenAI-compatible SDK."""
    from openai import AsyncOpenAI

    if not DEEPSEEK_API_KEY:
        yield _sse_event("error", {"message": "未配置 DEEPSEEK_API_KEY"})
        return

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    system_prompt = load_system_prompt()

    # Build messages
    session = _sessions.setdefault(session_id, [])

    user_text = message or "请查看这个文件的结构"
    if file_id:
        fpath = _find_file(file_id)
        if fpath:
            user_text += f"\n\n已上传文件: {os.path.basename(fpath)} (ID: {file_id})"
    if file_preview:
        user_text += f"\n\n文件内容预览:\n{json.dumps(file_preview, ensure_ascii=False, indent=2)}"

    session.append({"role": "user", "content": user_text})

    # Build OpenAI-format messages
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in session:
        api_messages.append({"role": msg["role"], "content": str(msg["content"])})

    tools = _to_openai_tools()
    max_turns = 5
    turn = 0
    full_response = ""

    while turn < max_turns:
        turn += 1
        try:
            response = await client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=api_messages,
                tools=tools,
                max_tokens=4096,
                stream=False,
            )
        except Exception as e:
            yield _sse_event("error", {"message": f"DeepSeek API 错误: {str(e)}"})
            return

        choice = response.choices[0]
        msg = choice.message

        # Check for tool calls
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)

                yield _sse_event("tool_call", {"tool": tool_name, "args": tool_args})

                result = execute_tool(tool_name, tool_args)
                yield _sse_event("tool_result", {"tool": tool_name, "success": result.get("success"), "summary": _summarize_result(tool_name, result)})

                # Add to messages
                api_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tc.function.arguments},
                    }],
                })
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
        else:
            # Text response
            text = msg.content or ""
            full_response += text
            yield _sse_event("text", {"text": text})
            break

    # Save response
    if full_response:
        session.append({"role": "assistant", "content": full_response})

    yield _sse_event("done", {})


def _summarize_result(tool_name: str, result: dict) -> str:
    """Create a brief summary of tool execution result."""
    if not result.get("success"):
        return f"失败: {result.get('error', '未知错误')}"

    data = result.get("data", {})
    if tool_name == "preview_excel_file":
        sheets = data.get("sheets", [])
        return f"共{data.get('sheet_count',0)}个Sheet: " + ", ".join(f"{s['name']}({s['rows']}行×{s['cols']}列)" for s in sheets)
    elif tool_name in ("parse_excel_auto", "parse_transposed_sum"):
        return f"解析{data.get('months',0)}个月数据，总用电{data.get('total_kwh',0):,.0f}kWh"
    elif tool_name == "run_full_analysis":
        sc = data.get("standard_comparison", {})
        return f"综合能耗{data.get('total_coal_tce',0)}tce，对标{sc.get('icon','')}{sc.get('level','')}"
    elif tool_name == "generate_word_report":
        return data.get("message", "报告已生成")
    return "执行成功"


def _sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event."""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"
