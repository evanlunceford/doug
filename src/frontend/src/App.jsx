import { BrowserRouter, Routes, Route } from "react-router-dom";

import Home from "./pages/Home";
import { LoaderProvider } from "./utils/LoaderContext";
import Layout from "./utils/Layout";



function App() {
  return (
    <LoaderProvider>
        <BrowserRouter>
            <Layout>
                <Routes>
                    <Route path="/" element={<Home />} />                
                </Routes>
            </Layout>
        </BrowserRouter>
    </LoaderProvider>

  );
}

export default App;