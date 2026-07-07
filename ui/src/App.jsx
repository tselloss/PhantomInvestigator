import { useState } from "react";
import "./App.css";
import StatusPill from "./components/StatusPill";
import FaultPanel from "./components/FaultPanel";
import Investigator from "./components/Investigator";
import ActivityFeed from "./components/ActivityFeed";

function App() {
  const [feedTick, setFeedTick] = useState(0);

  return (
    <>
      <header>
        <h1>👻 Phantom Investigator</h1>
        <StatusPill />
      </header>
      <main>
        <FaultPanel onChange={() => setFeedTick((t) => t + 1)} />
        <Investigator onFinished={() => setFeedTick((t) => t + 1)} />
        <ActivityFeed refreshKey={feedTick} />
      </main>
    </>
  );
}

export default App;
