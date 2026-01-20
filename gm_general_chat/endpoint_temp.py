@app.post("/chat", response_model=ChatResponse)
async def unified_chat_endpoint(request: ChatRequest):
    """
    Unified chat endpoint that handles:
    1. General conversation (no tools)
    2. Tool-enhanced conversation (with MCP tools)
    3. Different prompt modes (medical, pediatric, emergency, etc.)
    """
    try:
        # Generate session ID if not provided
        if not request.session:
            request.session = f"chat_{uuid.uuid4().hex[:12]}"

        # Detect language if auto
        detected_language = chat_config.detect_language(request.message)

        # Get chat engine with appropriate prompt mode
        chat_engine = await chat_config.get_or_create_chat_engine(
            request.session, request.prompt_mode
        )

        response_data = {}
        tool_used = None
        raw_tool_data = None
        llm_response_obj = None

        # Check if specific tool is requested
        if request.tools:
            logger.info(f"Processing tool-enhanced request: {request.tools.value}")

            # Extract search term from message
            search_term = await extract_medical_term(request.message, request.tools)

            # Execute tool search
            tool_result = await execute_tool_search(request.tools, search_term)

            if tool_result.success:
                # Lógica especial para ICD-10: respuesta directa sin LLM
                if request.tools == ToolType.ICD10:
                    # Para ICD-10, usar datos directos de la herramienta tal como vienen
                    response_data["response"] = tool_result.processed_result
                    tool_used = request.tools
                    raw_tool_data = tool_result.raw_result

                else:
                    # Para otras herramientas, usar prompt específico del YAML
                    tool_prompt_config = (
                        await chat_config.prompt_manager.get_tool_prompt(request.tools)
                    )
                    enhanced_prompt = tool_prompt_config.format(
                        user_message=request.message,
                        tool_data=tool_result.processed_result,
                    )

                    llm_response_obj = await asyncio.to_thread(
                        chat_engine.chat, enhanced_prompt
                    )
                    response_data["response"] = str(llm_response_obj)
                    tool_used = request.tools
                    raw_tool_data = tool_result.raw_result
            else:
                # Tool failed, use regular chat
                logger.warning(
                    f"Tool {request.tools.value} failed: {tool_result.error_message}"
                )
                llm_response_obj = await asyncio.to_thread(
                    chat_engine.chat, request.message
                )
                response_data["response"] = str(llm_response_obj)
                response_data["tool_error"] = tool_result.error_message
        else:
            # Regular chat without tools
            llm_response_obj = await asyncio.to_thread(
                chat_engine.chat, request.message
            )
            response_data["response"] = str(llm_response_obj)

        # Save conversation memory
        conversation_memory = ConversationMemory(
            user_message=request.message,
            tool_used=tool_used,
            raw_tool_data=raw_tool_data,
            assistant_response=response_data["response"],
            timestamp=datetime.now(),
            prompt_mode=request.prompt_mode,
            metadata={"language": detected_language, "session": request.session},
        )
        await chat_config.save_conversation_memory(request.session, conversation_memory)

        # Update session info
        await chat_config.update_session_info(
            request.session, tool_used, request.prompt_mode
        )

        # Get session info for response
        session_info = (
            await chat_config.redis_client.hgetall(f"session:{request.session}")
            if chat_config.redis_client
            else {}
        )
        message_count = int(session_info.get("message_count", "1"))

        # Prepare Response with Usage Metadata
        usage_metadata = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        if llm_response_obj:
            # 1. Try from metadata (LlamaIndex way)
            if hasattr(llm_response_obj, "metadata") and llm_response_obj.metadata:
                meta = llm_response_obj.metadata
                usage_metadata["prompt_tokens"] = meta.get("usage/prompt_tokens", 0)
                usage_metadata["completion_tokens"] = meta.get(
                    "usage/completion_tokens", 0
                )
                usage_metadata["total_tokens"] = meta.get("usage/total_tokens", 0)

            # 2. Try from raw (OpenAI style) if still zero
            if usage_metadata["total_tokens"] == 0 and hasattr(llm_response_obj, "raw"):
                raw = llm_response_obj.raw
                if hasattr(raw, "usage") and raw.usage:
                    usage_metadata = {
                        "prompt_tokens": getattr(raw.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(raw.usage, "completion_tokens", 0),
                        "total_tokens": getattr(raw.usage, "total_tokens", 0),
                    }

        return ChatResponse(
            status=ResponseStatus.SUCCESS,
            data=response_data,
            message="Chat processed successfully",
            session_id=request.session,
            timestamp=datetime.now(),
            provider=chat_config.provider_manager.current_provider,
            tool_used=tool_used,
            language_detected=detected_language,
            conversation_count=message_count,
            prompt_mode_used=request.prompt_mode,
            usage=usage_metadata,
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return ChatResponse(
            status=ResponseStatus.ERROR,
            data={"error": str(e)},
            message=f"Chat processing failed: {str(e)}",
            session_id=request.session,
            timestamp=datetime.now(),
            provider=(
                chat_config.provider_manager.current_provider
                if chat_config.provider_manager
                else "unknown"
            ),
        )
