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
            const detailMessage = typeof detail === "string"
                ? detail
                : Array.isArray(detail)
                ? detail.map((item) => item?.msg || JSON.stringify(item)).join("; ")
                : undefined;
            const status = error.response.status;

            if (status === 401 || status === 403) {
                return detailMessage
                    ? `Backend authentication/configuration failure (HTTP ${status}): ${detailMessage}`
                    : `Backend authentication/configuration failure (HTTP ${status}).`;
            }

            if (status === 404) {
                return detailMessage
                    ? `API endpoint not found (HTTP 404): ${detailMessage}`
                    : "API endpoint not found (HTTP 404).";
            }

            if (status === 422) {
                return detailMessage
                    ? `The backend rejected the request (HTTP 422): ${detailMessage}`
                    : "The backend rejected the request (HTTP 422).";
            }

            if (detailMessage) {
                return `Backend request failed with HTTP ${status}: ${detailMessage}`;
            }

            return `Backend request failed with HTTP ${status}.`;
        }

        if (error.code === "ECONNABORTED") {
            return "The backend request timed out.";
        }

        if (error.code === "ERR_NETWORK") {
            return "Network error: the API request could not complete. Check backend reachability and browser CORS settings.";
        }

        return error.message || "The API request could not complete.";
    }

    return "An unexpected error occurred.";
}
