import { BrowserRouter, Routes, Route } from "react-router-dom";

import Home from "./pages/Home";
import { LoaderProvider } from "./utils/LoaderContext";
import Layout from "./utils/Layout";
import Tasks from "./pages/Tasks";



function App() {
  return (
    <LoaderProvider>
        <BrowserRouter>
            <Layout>
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/tasks" element={<Tasks />} />           
                </Routes>
            </Layout>
        </BrowserRouter>
    </LoaderProvider>

  );
}

export default App;