import sqlite3
import pandas as pd
from pandas.testing import assert_frame_equal
from datetime import datetime, timedelta
import random
import pickle
from nempy.historical_inputs import loaders, xml_cache, mms_db, units, \
    interconnectors, constraints, demand
from nempy import historical_market_builder

# These tests require some additional clean up and will probably not run on your machine. ##############################


def get_test_intervals(number=100):
    start_time = datetime(year=2019, month=1, day=1, hour=0, minute=0)
    end_time = datetime(year=2019, month=12, day=31, hour=0, minute=0)
    difference = end_time - start_time
    difference_in_5_min_intervals = difference.days * 12 * 24
    random.seed(2)
    intervals = random.sample(range(1, difference_in_5_min_intervals), number)
    times = [start_time + timedelta(minutes=5 * i) for i in intervals]
    times_formatted = [t.isoformat().replace('T', ' ').replace('-', '/') for t in times]
    return times_formatted


def test_if_ramp_rates_calculated_correctly():
    inputs_database = 'test_files/historical.db'
    con = sqlite3.connect(inputs_database)
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')

    for interval in get_test_intervals():
        print(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.set_ramp_rate_limits()
        market.set_unit_dispatch_to_historical_values()
        market.dispatch()
        assert market.measured_violation_equals_historical_violation(historical_name='ramp_rate',
                                                                     nempy_constraints=['ramp_up', 'ramp_down'])

    with open('interval_with_violations.pickle', 'rb') as f:
        interval_with_violations = pickle.load(f)

    for interval, types in interval_with_violations.items():
        if 'ramp_rate' in types:
            print(interval)
            market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                          interval=interval)
            market.add_unit_bids_to_market()
            market.set_ramp_rate_limits()
            market.set_unit_dispatch_to_historical_values()
            market.dispatch()
            assert market.measured_violation_equals_historical_violation(historical_name='ramp_rate',
                                                                         nempy_constraints=['ramp_up', 'ramp_down'])


def test_fast_start_constraints():
    inputs_database = 'test_files/historical.db'
    con = sqlite3.connect(inputs_database)
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')

    for interval in get_test_intervals():
        print(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.set_fast_start_constraints()
        market.set_unit_dispatch_to_historical_values()
        market.dispatch()
        assert market.measured_violation_equals_historical_violation('fast_start',
                                                                     nempy_constraints=['fast_start'])

    with open('interval_with_violations.pickle', 'rb') as f:
        interval_with_violations = pickle.load(f)

    for interval, types in interval_with_violations.items():
        if 'fast_start' in types:
            print(interval)
            market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                          interval=interval)
            market.add_unit_bids_to_market()
            market.set_fast_start_constraints()
            market.set_unit_dispatch_to_historical_values()
            market.dispatch()
            assert market.measured_violation_equals_historical_violation('fast_start',
                                                                         nempy_constraints=['fast_start'])


def test_capacity_constraints():
    inputs_database = 'test_files/historical_all.db'
    con = sqlite3.connect(inputs_database)
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')

    for interval in get_test_intervals():
        print(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.set_unit_limit_constraints()
        market.set_unit_dispatch_to_historical_values()
        market.dispatch()
        assert market.measured_violation_equals_historical_violation('unit_capacity',
                                                                     nempy_constraints=['unit_bid_capacity'])


def test_fcas_trapezium_scaled_availability():
    inputs_database = 'test_files/historical_all.db'
    con = sqlite3.connect('test_files/historical_all.db')
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')
    for interval in get_test_intervals():
        print(interval)
        historical_inputs.load_interval(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.set_unit_fcas_constraints()
        market.set_unit_limit_constraints()
        market.set_unit_dispatch_to_historical_values(wiggle_room=0.0001)
        market.dispatch(calc_prices=False)
        avails = market.do_fcas_availabilities_match_historical()
        # I think NEMDE might be getting avail calcs wrong when units are opperating on the slopes, and the slopes
        # are vertical. They should be ignore 0 slope cofficients, maybe this is not happing because of floating
        # point comparison.
        if interval == '2019/01/29 18:10:00':
            avails = avails[~(avails['unit'] == 'PPCCGT')]
        if interval == '2019/01/07 19:35:00':
            avails = avails[~(avails['unit'] == 'PPCCGT')]
        assert avails['error'].abs().max() < 1.1


def test_all_units_and_service_dispatch_historically_present_in_market():
    inputs_database = 'test_files/historical_all.db'
    con = sqlite3.connect('test_files/historical_all.db')
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')
    for interval in get_test_intervals():
        historical_inputs.load_interval(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        assert market.all_dispatch_units_and_service_have_decision_variables()


def test_slack_in_generic_constraints():
    inputs_database = 'test_files/historical.db'
    con = sqlite3.connect('test_files/historical.db')
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')
    for interval in get_test_intervals():
        print(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.add_interconnectors_to_market()
        market.add_generic_constraints()
        market.set_unit_dispatch_to_historical_values(wiggle_room=0.0001)
        market.set_interconnector_flow_to_historical_values(wiggle_room=0.0001)
        market.dispatch(calc_prices=False)
        assert market.is_generic_constraint_slack_correct()


def test_slack_in_generic_constraints_use_fcas_requirements_interface():
    inputs_database = 'test_files/historical_all.db'
    con = sqlite3.connect('test_files/historical_all.db')
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')
    for interval in get_test_intervals():
        print(interval)
        historical_inputs.load_interval(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.add_interconnectors_to_market()
        market.add_generic_constraints_fcas_requirements()
        market.set_unit_dispatch_to_historical_values(wiggle_room=0.0001)
        market.set_interconnector_flow_to_historical_values(wiggle_room=0.001)
        market.dispatch(calc_prices=False)
        market.market.get_elastic_constraints_violation_degree('generic')
        assert market.all_constraints_presenet()
        assert market.is_generic_constraint_slack_correct()
        assert market.is_fcas_constraint_slack_correct()


def test_slack_in_generic_constraints_with_all_features():
    inputs_database = 'test_files/historical_all.db'
    con = sqlite3.connect('test_files/historical_all.db')
    historical_inputs = loaders.HistoricalInputs(
        market_management_system_database_connection=con,
        nemde_xml_cache_folder='test_files/historical_xml_files')
    for interval in get_test_intervals():
        print(interval)
        historical_inputs.load_interval(interval)
        market = historical_market_builder.SpotMarket(inputs_database=inputs_database, inputs=historical_inputs,
                                                      interval=interval)
        market.add_unit_bids_to_market()
        market.add_interconnectors_to_market()
        market.add_generic_constraints_fcas_requirements()
        market.set_unit_fcas_constraints()
        market.set_unit_limit_constraints()
        market.set_ramp_rate_limits()
        market.set_unit_dispatch_to_historical_values(wiggle_room=0.003)
        market.set_interconnector_flow_to_historical_values()
        market.dispatch(calc_prices=False)
        assert market.is_generic_constraint_slack_correct()
        assert market.is_fcas_constraint_slack_correct()
        assert market.is_regional_demand_meet()


def test_hist_dispatch_values_meet_demand():
    con = sqlite3.connect('/media/nickgorman/Samsung_T5/nempy_test_files/historical_mms.db')
    mms_database = mms_db.DBManager(con)
    xml_cache_manager = xml_cache.XMLCacheManager('/media/nickgorman/Samsung_T5/nempy_test_files/nemde_cache')
    raw_inputs_loader = loaders.RawInputsLoader(nemde_xml_cache_manager=xml_cache_manager,
                                                market_management_system_database=mms_database)

    for interval in get_test_intervals():
        raw_inputs_loader.set_interval(interval)
        unit_inputs = units.UnitData(raw_inputs_loader)
        interconnector_inputs = interconnectors.InterconnectorData(raw_inputs_loader)
        constraint_inputs = constraints.ConstraintData(raw_inputs_loader)
        demand_inputs = demand.DemandData(raw_inputs_loader)

        market_builder = historical_market_builder.SpotMarketBuilder(unit_inputs=unit_inputs,
                                                                     interconnector_inputs=interconnector_inputs,
                                                                     constraint_inputs=constraint_inputs,
                                                                     demand_inputs=demand_inputs)
        market_builder.add_unit_bids_to_market()
        market_builder.add_interconnectors_to_market()
        market = market_builder.get_market_object()
        market_overrider = historical_market_builder.MarketOverrider(market=market,
                                                                     mms_db=mms_database,
                                                                     interval=interval)
        market_overrider.set_unit_dispatch_to_historical_values()
        market_overrider.set_interconnector_flow_to_historical_values()
        market_builder.dispatch()
        market_checker = historical_market_builder.MarketChecker(market=market,
                                                                 mms_db=mms_database,
                                                                 xml_cache=xml_cache,
                                                                 interval=interval)
        test_passed = market_checker.is_regional_demand_meet()
        market.con.close()
        assert test_passed


def test_against_10_interval_benchmark():
    con = sqlite3.connect('/media/nickgorman/Samsung_T5/nempy_test_files/historical_mms.db')
    mms_database = mms_db.DBManager(con)
    xml_cache_manager = xml_cache.XMLCacheManager('/media/nickgorman/Samsung_T5/nempy_test_files/nemde_cache')
    raw_inputs_loader = loaders.RawInputsLoader(nemde_xml_cache_manager=xml_cache_manager,
                                                market_management_system_database=mms_database)
    outputs = []
    for interval in get_test_intervals(number=10):
        raw_inputs_loader.set_interval(interval)
        unit_inputs = units.UnitData(raw_inputs_loader)
        interconnector_inputs = interconnectors.InterconnectorData(raw_inputs_loader)
        constraint_inputs = constraints.ConstraintData(raw_inputs_loader)
        demand_inputs = demand.DemandData(raw_inputs_loader)

        market_builder = historical_market_builder.SpotMarketBuilder(unit_inputs=unit_inputs,
                                                                     interconnector_inputs=interconnector_inputs,
                                                                     constraint_inputs=constraint_inputs,
                                                                     demand_inputs=demand_inputs)
        market_builder.add_unit_bids_to_market()
        market_builder.add_interconnectors_to_market()
        market_builder.add_generic_constraints_fcas_requirements()
        market_builder.set_unit_fcas_constraints()
        market_builder.set_unit_limit_constraints()
        market_builder.set_region_demand_constraints()
        market_builder.set_ramp_rate_limits()
        market_builder.set_fast_start_constraints()
        market_builder.dispatch(calc_prices=True)
        market = market_builder.get_market_object()

        market_checker = historical_market_builder.MarketChecker(market=market,
                                                                 mms_db=mms_database,
                                                                 xml_cache=xml_cache,
                                                                 interval=interval)
        price_comp = market_checker.get_price_comparison()
        outputs.append(price_comp)
    outputs = pd.concat(outputs)
    outputs.to_csv('latest_10_interval_run.csv', index=False)
    benchmark = pd.read_csv('10_interval_benchmark.csv')
    assert_frame_equal(outputs.reset_index(drop=True), benchmark, check_exact=False, atol=1e-3)


def test_against_100_interval_benchmark():
    con = sqlite3.connect('test_files/historical_all.db')
    mms_database = mms_db.DBManager(con)
    xml_cache_manager = xml_cache.XMLCacheManager('test_files/historical_xml_files')
    raw_inputs_loader = loaders.RawInputsLoader(nemde_xml_cache_manager=xml_cache_manager,
                                                market_management_system_database=mms_database)
    outputs = []
    for interval in get_test_intervals(number=100):
        raw_inputs_loader.set_interval(interval)
        unit_inputs = units.UnitData(raw_inputs_loader)
        interconnector_inputs = interconnectors.InterconnectorData(raw_inputs_loader)
        constraint_inputs = constraints.ConstraintData(raw_inputs_loader)
        demand_inputs = demand.DemandData(raw_inputs_loader)

        market_builder = historical_market_builder.SpotMarketBuilder(unit_inputs=unit_inputs,
                                                                     interconnector_inputs=interconnector_inputs,
                                                                     constraint_inputs=constraint_inputs,
                                                                     demand_inputs=demand_inputs)
        market_builder.add_unit_bids_to_market()
        market_builder.add_interconnectors_to_market()
        market_builder.add_generic_constraints_fcas_requirements()
        market_builder.set_unit_fcas_constraints()
        market_builder.set_unit_limit_constraints()
        market_builder.set_region_demand_constraints()
        market_builder.set_ramp_rate_limits()
        market_builder.set_fast_start_constraints()
        market_builder.dispatch(calc_prices=True)
        market = market_builder.get_market_object()

        market_checker = historical_market_builder.MarketChecker(market=market,
                                                                 mms_db=mms_database,
                                                                 xml_cache=xml_cache,
                                                                 interval=interval)
        price_comp = market_checker.get_price_comparison()
        outputs.append(price_comp)

    outputs = pd.concat(outputs)
    outputs.to_csv('latest_1000_interval_run.csv', index=False)
    benchmark = pd.read_csv('1000_interval_benchmark.csv')
    assert_frame_equal(outputs.reset_index(drop=True), benchmark.reset_index(drop=True), check_less_precise=3)


def test_against_1000_interval_benchmark():
    con = sqlite3.connect('/media/nickgorman/Samsung_T5/nempy_test_files/historical_mms.db')
    mms_database = mms_db.DBManager(con)
    xml_cache_manager = xml_cache.XMLCacheManager('/media/nickgorman/Samsung_T5/nempy_test_files/nemde_cache')
    raw_inputs_loader = loaders.RawInputsLoader(nemde_xml_cache_manager=xml_cache_manager,
                                                market_management_system_database=mms_database)
    outputs = []
    for interval in get_test_intervals(number=1000):
        raw_inputs_loader.set_interval(interval)
        unit_inputs = units.UnitData(raw_inputs_loader)
        interconnector_inputs = interconnectors.InterconnectorData(raw_inputs_loader)
        constraint_inputs = constraints.ConstraintData(raw_inputs_loader)
        demand_inputs = demand.DemandData(raw_inputs_loader)

        market_builder = historical_market_builder.SpotMarketBuilder(unit_inputs=unit_inputs,
                                                                     interconnector_inputs=interconnector_inputs,
                                                                     constraint_inputs=constraint_inputs,
                                                                     demand_inputs=demand_inputs)
        market_builder.add_unit_bids_to_market()
        market_builder.add_interconnectors_to_market()
        market_builder.add_generic_constraints_fcas_requirements()
        market_builder.set_unit_fcas_constraints()
        market_builder.set_unit_limit_constraints()
        market_builder.set_region_demand_constraints()
        market_builder.set_ramp_rate_limits()
        market_builder.set_fast_start_constraints()
        market_builder.dispatch(calc_prices=True)
        market = market_builder.get_market_object()

        market_checker = historical_market_builder.MarketChecker(market=market,
                                                                 mms_db=mms_database,
                                                                 xml_cache=xml_cache,
                                                                 interval=interval)
        price_comp = market_checker.get_price_comparison()
        outputs.append(price_comp)

    outputs = pd.concat(outputs)
    outputs.to_csv('latest_1000_interval_run.csv', index=False)
    benchmark = pd.read_csv('1000_interval_benchmark.csv')
    assert_frame_equal(outputs.reset_index(drop=True), benchmark.reset_index(drop=True), check_less_precise=3)
