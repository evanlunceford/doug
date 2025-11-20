const BASE_URL =
  import.meta.env.MODE === "development"
    ? import.meta.env.VITE_API_URL_DEV
    : import.meta.env.VITE_API_URL_PROD;



// A simple wrapper around fetch
async function request(endpoint, method = "GET", data = null, headers = {}) {
  if (!BASE_URL) {
    throw new Error("BASE_URL is not defined. Check your REACT_APP_API_URL_* env vars.");
  }

  const config = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  if (data) {
    config.body = JSON.stringify(data);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `API Error (${response.status}): ${errorText || response.statusText}`
    );
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

const Api = {
  get: (endpoint, headers = {}) =>
    request(endpoint, "GET", null, headers),

  post: (endpoint, data, headers = {}) =>
    request(endpoint, "POST", data, headers),

  put: (endpoint, data, headers = {}) =>
    request(endpoint, "PUT", data, headers),

  delete: (endpoint, headers = {}) =>
    request(endpoint, "DELETE", null, headers),
};

export default Api;
