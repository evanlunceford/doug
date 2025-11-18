import { useLoader } from './LoaderContext';
import LoadingScreen from './LoadingScreen';
import Sidebar from './Sidebar';
import '../css/app.css';

function Layout({ children, contentClassName = '', contentStyle = {} }) {
  const { isLoading, fadeOut } = useLoader();

  return (
    <div className="app-container">
        <Sidebar />
        <main className={`content-area ${contentClassName}`} id="contentArea" style={contentStyle}>
            {isLoading && <LoadingScreen fadeOut={fadeOut} />}
            {children}
        </main>
    </div>
  );
}

export default Layout;
