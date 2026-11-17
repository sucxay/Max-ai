# Voice input

Run `/voice` in the MAX CLI to capture one spoken request. Recording starts
immediately, ends after 1.2 seconds of silence, and is limited to 30 seconds.
The transcript is passed to the same LangGraph flow as typed input. Run
`/voice` again for another request.

Transcription uses Parakeet MLX locally. The default model is
`mlx-community/parakeet-tdt-0.6b-v3`; set `PARAKEET_MODEL` to select another
compatible model. The model is downloaded to the Hugging Face cache on first
use. Set `MAX_VOICE_RMS_THRESHOLD` if the microphone's input level needs a
different speech detection threshold.
