

const LoadingScreen = ({ fadeOut }) => {
  return (
    <div className={`loading-overlay ${fadeOut ? 'fade-out' : ''}`}>
      <div className="loader"></div>
    </div>
  );
};

export default LoadingScreen;
