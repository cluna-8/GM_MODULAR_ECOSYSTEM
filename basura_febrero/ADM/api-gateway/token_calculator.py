import tiktoken
import logging

logger = logging.getLogger(__name__)

def get_encoding_for_model(model_name: str = "gpt-3.5-turbo"):
    """Get tiktoken encoding for model"""
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        logger.warning(f"Model {model_name} not found, using cl100k_base")
        return tiktoken.get_encoding("cl100k_base")

def count_tokens_in_text(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in a text string"""
    try:
        encoding = get_encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        # Fallback: rough estimation (1 token ≈ 4 chars)
        return len(text) // 4

def analyze_medical_request(request_data: dict, response_data: dict, model: str = "gpt-3.5-turbo") -> dict:
    """Analyze tokens for medical API request"""
    try:
        # Extract input text
        input_text = request_data.get("message", "")
        
        # Extract output text - verificar estructura correcta
        output_text = ""
        if isinstance(response_data, dict):
            if "data" in response_data and "response" in response_data["data"]:
                output_text = response_data["data"]["response"]
            else:
                output_text = response_data.get("response", "") or response_data.get("answer", "")
        
        # Count tokens
        input_tokens = count_tokens_in_text(input_text, model)
        output_tokens = count_tokens_in_text(output_text, model)
        total_tokens = input_tokens + output_tokens
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens
        }
        
    except Exception as e:
        logger.error(f"Error analyzing request: {e}")
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }