"""Launch the editor API. UI: cd web && npm run dev → http://localhost:5173"""
import uvicorn


def main():
    uvicorn.run(
        "app.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
