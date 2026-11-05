import axios from "axios";

const baseURL = (
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8001"
).replace(/\/+$/, "");

export const apiClient = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
        Accept: "application/json",
    },
});

export function getApiErrorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        if (error.response) {
            const detail = error.response.data?.detail;

            if (typeof detail === "string") {
                return detail;
            }

            return `Backend request failed with HTTP ${error.response.status}.`;
        }

        if (error.code === "ECONNABORTED") {
            return "The backend request timed out.";
        }

        return "Cannot connect to the backend. Check that FastAPI is running.";
    }

    return "An unexpected error occurred.";
}
