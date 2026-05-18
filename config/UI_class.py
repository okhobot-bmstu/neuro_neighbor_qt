Options = {
    "cache_dir": ("dir", "Кэш"),
    "hf_token": ("text", "HF Token"),
    "offline": ("check", "Офлайн режим"),

    "model.repo_id": ("text", "Repo ID"),
    "model.filename": ("text", "Filename"),
    "model.init_prompt_path": ("text", "Init Prompt Path"),
    "model.chat_history_path": ("text", "Chat History Path"),
    "model.init_prompt_role": ("combo", "Init Prompt Role", ["user", "system", "assistant"]),
    "model.max_console_op_depth": ("text", "Max Depth"),
    "model.load_embeddings_count": ("text", "Embeddings"),
    "model.chat_size": ("text", "Chat Size"),
    "model.use_gpu": ("check", "Use GPU"),

    "tts.pitch_shift": ("text", "Pitch Shift"),
    "tts.speaker_name": ("text", "Speaker"),
    "tts.model_name": ("text", "Model Name"),

    "stt.model": ("combo", "Model", ["tiny", "base", "small", "medium", "large"]),
    "stt.device": ("combo", "Device", ["cpu", "cuda"]),
    "stt.use_nr": ("check", "Use NR"),
    "stt.micro_index": ("mic", "Microphone"),
    "stt.silence_duration": ("text", "Silence Duration"),
}

Headers = [
    ("Основные", ["cache_dir", "hf_token", "offline"]),
    ("Модель", [
        "model.repo_id", "model.filename", "model.init_prompt_path",
        "model.chat_history_path", "model.init_prompt_role",
        "model.max_console_op_depth", "model.load_embeddings_count",
        "model.chat_size", "model.use_gpu",
    ]),
    ("TTS", ["tts.pitch_shift", "tts.speaker_name", "tts.model_name"]),
    ("STT", ["stt.model", "stt.device", "stt.use_nr", "stt.silence_duration", "stt.micro_index"]),
]