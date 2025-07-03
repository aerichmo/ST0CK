import asyncio
import logging
import config
import os

# Import the core components of the application. Each component is designed
# to run as an independent, asynchronous task.
from market.state import MarketDataManager
from engine.delta_engine import DeltaEngine
from portfolio.position_manager import PositionManager
from strategy.hedging_strategy import TradingStrategy
from strategy.options_strategy import open_initial_straddle

# Set up the root logger according to the configuration.
# This allows for consistent logging across all modules.
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['SSL_CERT_DIR'] = ''
except ImportError:
    pass

async def main():
    """
    The main orchestration function for the Gamma Scalper application.

    This function is responsible for:
    1. Initializing all the major components (PositionManager, MarketDataManager, etc.).
    2. Setting up the asynchronous queues that the components use to communicate.
    3. Performing the initial setup of the trading position (either 'init' or 'resume').
    4. Creating and running the main asynchronous tasks for each component.
    5. Handling graceful shutdown on user interruption (Ctrl+C).
    """
    # An asyncio.Event to signal a graceful shutdown to all concurrent tasks.
    shutdown_event = asyncio.Event()

    # --- Initialize Communication Queues ---
    # These queues are the backbone of the application's event-driven architecture.
    # They are intentionally set to a maxsize of 1. This means they only ever
    # hold the most recent message, preventing a backlog of stale data/commands.
    # For example, if the Delta Engine is busy and the market moves again, the
    # old trigger is simply replaced with the new one.

    # Queue for the TradingStrategy to send trade commands to the PositionManager.
    trade_action_queue = asyncio.Queue(maxsize=1)
    # Queue for the MarketDataManager to trigger a new delta calculation in the DeltaEngine.
    trigger_queue = asyncio.Queue(maxsize=1)
    # Queue for the DeltaEngine to send the newly calculated portfolio delta to the TradingStrategy.
    delta_queue = asyncio.Queue(maxsize=1)

    # --- Instantiate Components and Inject Dependencies ---
    # The components are initialized with the necessary queues and events to
    # facilitate communication and coordination.

    # The PositionManager is the execution layer, handling all interactions with the Alpaca API.
    position_manager = PositionManager(trade_action_queue, shutdown_event)

    # --- Perform one-time setup based on the configured INITIALIZATION_MODE ---
    await position_manager.initialize_position()
    # A brief pause to allow for any liquidations to be processed by the API.
    await asyncio.sleep(5)

    # The fill_listener must be started *before* we place any new orders.
    # This ensures that we capture the fill events for our initial straddle.
    fill_listener_task = asyncio.create_task(position_manager.fill_listener_loop())
    await asyncio.sleep(5)  # Wait for the listener to subscribe to trade updates.

    # If in 'init' mode, the application finds and opens a new straddle position.
    if config.INITIALIZATION_MODE == 'init':
        await open_initial_straddle(position_manager)

    # A critical check: if we don't have a call and put option after initialization,
    # the strategy cannot run. This could happen if no suitable straddle was found.
    if position_manager.call_option_symbol is None or position_manager.put_option_symbol is None:
        logger.critical("Failed to find an initial straddle position. Cannot start strategy. Exiting.")
        fill_listener_task.cancel()  # Clean up the running listener task.
        return  # Exit the application.

    logger.info("Initializing application components...")

    # The MarketDataManager subscribes to real-time market data for the underlying
    # and the selected options, feeding price updates into the system.
    market_manager = MarketDataManager(
        trigger_queue,
        position_manager.call_option_symbol,
        position_manager.put_option_symbol
    )

    # The DeltaEngine is the computational core, calculating the options delta
    # when triggered by the MarketDataManager.
    delta_engine = DeltaEngine(market_manager, trigger_queue, delta_queue, shutdown_event)

    # The TradingStrategy is the decision-making layer. It receives delta updates
    # and decides when to send a hedging trade command to the PositionManager.
    trading_strategy = TradingStrategy(position_manager, delta_queue, trade_action_queue, shutdown_event)

    # --- Create and Run Concurrent Tasks ---
    # Each component's main logic is encapsulated in a 'run' method or similar
    # async loop. We gather them all into a list of tasks to be run by asyncio.
    tasks = [
        market_manager.run(),
        position_manager.trade_executor_loop(),
        delta_engine.run(),
        trading_strategy.run(),
        fill_listener_task  
    ]

    logger.info("Application starting. Press Ctrl+C to shut down gracefully.")

    # --- Run until interrupted ---
    # This is the main application loop. asyncio.gather runs all tasks concurrently.
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Cleaning up...")
        # Set the shutdown event to signal all tasks to terminate their loops.
        shutdown_event.set()
        # Wait for all tasks to finish their cleanup and exit.
        # return_exceptions=True prevents the program from crashing if a task raises an exception on cancellation.
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Application has shut down.")


if __name__ == "__main__":
    # The entry point of the script. asyncio.run() starts the event loop
    # and runs the main() coroutine until it completes.
    asyncio.run(main())
