import { createContext, useContext, useState, useCallback } from 'react';

const LoaderContext = createContext();

export const useLoader = () => useContext(LoaderContext);

export const LoaderProvider = ({ children }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

    const startLoading = useCallback(() => {
    setIsLoading(true);
    setFadeOut(false);
    }, []);

    const stopLoading = useCallback(() => {
    setFadeOut(true);
    setTimeout(() => setIsLoading(false), 500);
    }, []);

  return (
    <LoaderContext.Provider value={{ isLoading, fadeOut, startLoading, stopLoading }}>
      {children}
    </LoaderContext.Provider>
  );
};
