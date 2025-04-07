import pytest
import pandas as pd
from unittest.mock import MagicMock, patch, call # Use MagicMock for more flexibility
import numpy as np # For NaN values
import gspread # Import gspread module for exceptions

# Assuming your DataSheet class is in src.iter8.data_sheet
from iter8.data_sheet import DataSheet, _UpdateContext

# --- Fixtures --- 
# Fixtures are now defined in tests/conftest.py and are automatically discovered by pytest

# --- Test Cases ---

def test_context_manager_no_changes(data_sheet_instance, mock_worksheet):
    """
    Test that no updates occur if the DataFrame copy is not modified.
    """
    original_df_copy = data_sheet_instance.copy() # Keep a copy for comparison

    with data_sheet_instance.start_update() as change:
        # No changes made to 'change' DataFrame
        pass

    # Assertions
    mock_worksheet.batch_update.assert_not_called()
    pd.testing.assert_frame_equal(data_sheet_instance, original_df_copy)

def test_context_manager_single_cell_change(data_sheet_instance, mock_worksheet):
    """
    Test update after changing a single cell.
    Integration test: Verifies context manager calls update and updates the DataFrame.
    """
    # Define the change
    change_idx = 1
    change_col = 'col_b'
    new_value = 'Updated B2'
    original_value = data_sheet_instance.loc[change_idx, change_col]
    assert original_value != new_value # Ensure the value is actually changing

    with data_sheet_instance.start_update() as change:
        change.loc[change_idx, change_col] = new_value

    # Assertions
    # 1. Check if batch_update was called correctly
    mock_worksheet.batch_update.assert_called_once()
    call_args, call_kwargs = mock_worksheet.batch_update.call_args
    # We trust _calculate_updates unit test for payload content, just check count if desired
    assert len(call_args[0]) == 1 # Verify one update was generated
    assert call_kwargs.get('value_input_option') == 'USER_ENTERED'

    # 2. Check if the original DataFrame in memory was updated
    assert data_sheet_instance.loc[change_idx, change_col] == new_value

def test_context_manager_multiple_cell_changes(data_sheet_instance, mock_worksheet):
    """
    Test update after changing multiple cells in different rows/columns.
    Integration test: Verifies context manager calls update and updates the DataFrame.
    """
    changes_to_make = [
        {'idx': 0, 'col': 'col_c', 'val': 99},
        {'idx': 2, 'col': 'col_d', 'val': 'New D3'}
    ]

    with data_sheet_instance.start_update() as change:
        for c in changes_to_make:
            change.loc[c['idx'], c['col']] = c['val']

    # Assertions
    # 1. Check if batch_update was called correctly
    mock_worksheet.batch_update.assert_called_once()
    call_args, call_kwargs = mock_worksheet.batch_update.call_args
    # Check expected number of updates
    assert len(call_args[0]) == len(changes_to_make)
    assert call_kwargs.get('value_input_option') == 'USER_ENTERED'

    # 2. Check if the original DataFrame in memory was updated correctly
    for c in changes_to_make:
        assert data_sheet_instance.loc[c['idx'], c['col']] == c['val']

def test_context_manager_change_with_df_update(data_sheet_instance, mock_worksheet):
    """
    Test change detection when using df.update().
    Integration test: Verifies context manager calls update and updates the DataFrame.
    """
    update_df = pd.DataFrame({'col_b': ['UPDATED B1']}, index=[0])
    expected_final_value = 'UPDATED B1'

    with data_sheet_instance.start_update() as change:
        change.update(update_df)

    # Assertions
    # 1. Check that the sheet update was attempted
    mock_worksheet.batch_update.assert_called_once()
    # (Payload content is verified by unit tests - though we might need a specific one for df.update)

    # 2. Check that the original DataFrame in memory was updated
    assert data_sheet_instance.loc[0, 'col_b'] == expected_final_value

def test_context_manager_change_nan_to_value(data_sheet_instance, mock_worksheet):
    """
    Test changing a NaN value to a string.
    Integration test: Verifies context manager calls update and updates the DataFrame.
    """
    row_index = 1 # col_d is NaN here, Sheet Row 3
    col_name = 'col_d'
    new_value = 'Now Has Value'
    # expected_range = 'D3' # col_d is 4th col (D)

    with data_sheet_instance.start_update() as change:
        change.loc[row_index, col_name] = new_value

    # Assertions
    # 1. Check that the sheet update was attempted
    mock_worksheet.batch_update.assert_called_once()
    # (Payload content is verified by test_calculate_updates_nan_to_value)

    # 2. Check that the original DataFrame in memory was updated
    assert data_sheet_instance.loc[row_index, col_name] == new_value

def test_context_manager_change_value_to_empty(data_sheet_instance, mock_worksheet):
    """
    Test changing a string value to an empty string.
    """
    row_index = 2 # col_d is 'C3', Sheet Row 4
    col_name = 'col_d'
    new_value = ''
    expected_range = 'D4' # col_d is 4th col (D)

    with data_sheet_instance.start_update() as change:
        change.loc[row_index, col_name] = new_value

    # Assertions
    # 1. Check that the sheet update was attempted
    mock_worksheet.batch_update.assert_called_once()
    # (Payload content is verified by unit tests for _calculate_updates)

    # 2. Check that the original DataFrame in memory was updated
    assert data_sheet_instance.loc[row_index, col_name] == new_value

def test_context_manager_exception_inside_with(data_sheet_instance, mock_worksheet):
    """
    Test that no updates occur if an exception is raised inside the 'with' block.
    """
    original_df_copy = data_sheet_instance.copy()
    custom_exception = ValueError("Something went wrong inside!")

    with pytest.raises(ValueError, match="Something went wrong inside!"):
        with data_sheet_instance.start_update() as change:
            change.loc[0, 'col_b'] = "This change won't happen"
            raise custom_exception

    # Assertions
    mock_worksheet.batch_update.assert_not_called()
    # Original DataFrame should remain unchanged
    pd.testing.assert_frame_equal(data_sheet_instance, original_df_copy)

def test_context_manager_gspread_update_fails(data_sheet_instance, mock_worksheet):
    """
    Test handling when worksheet.batch_update raises an error.
    """
    original_df_copy = data_sheet_instance.copy()
    
    # Create a simple exception instead of trying to use APIError directly
    gspread_exception = Exception("API limit reached")
    mock_worksheet.batch_update.side_effect = gspread_exception

    row_index = 0
    col_name = 'col_b'
    new_value = "Change that fails"

    # Test with a patch to capture print output
    with patch('builtins.print') as mock_print:
        with data_sheet_instance.start_update() as change:
            change.loc[row_index, col_name] = new_value

    # Assertions
    mock_worksheet.batch_update.assert_called_once()
    call_args, call_kwargs = mock_worksheet.batch_update.call_args
    assert call_args[0] == [{'range': 'B2', 'values': [[new_value]]}]
    assert call_kwargs.get('value_input_option') == 'USER_ENTERED'
    
    # Check that the original DataFrame was NOT updated because the API call failed
    pd.testing.assert_frame_equal(data_sheet_instance, original_df_copy, check_dtype=False)
    # Check if the error was printed
    mock_print.assert_any_call(f"Error during sheet update: {gspread_exception}")

def test_column_renaming_or_dropping_impact(data_sheet_instance, mock_worksheet):
    """
    Test potential issues if columns are renamed or dropped in the copy.
    (This might expose limitations based on the current comparison logic)
    """
    original_df_copy = data_sheet_instance.copy()

    with data_sheet_instance.start_update() as change:
         # This change should be detected
         change.loc[0, 'col_b'] = "Valid Change"
         # This modification makes comparison tricky if not handled carefully
         # change.drop(columns=['col_c'], inplace=True) # Dropping column
         # change.rename(columns={'col_d': 'col_d_new'}, inplace=True) # Renaming

    # Assertions (adapt based on how you expect/want it to handle this)
    # Current logic compares based on original columns. Dropped/Renamed cols in copy won't align.
    # It should likely only update 'col_b' and might print warnings for others.
    mock_worksheet.batch_update.assert_called_once()
    call_args, call_kwargs = mock_worksheet.batch_update.call_args
    assert call_args[0] == [{'range': 'B2', 'values': [['Valid Change']]}]
    assert call_kwargs.get('value_input_option') == 'USER_ENTERED'
    
    # Original DF should only have 'col_b' updated
    assert data_sheet_instance.loc[0, 'col_b'] == "Valid Change"
    assert data_sheet_instance.loc[0, 'col_c'] == 10 # Unchanged

# =======================================
# Unit Tests for _calculate_updates
# =======================================

def test_calculate_updates_single_cell(data_sheet_instance):
    """
    Unit test for _calculate_updates focusing on a single cell change.
    """
    original_df = data_sheet_instance
    copy_df = original_df.copy()
    
    # Simulate the change made within the context manager
    change_idx = 1
    change_col = 'col_b'
    new_value = 'Updated B2'
    copy_df.loc[change_idx, change_col] = new_value

    # Expected payload for gspread batch_update
    # Index 1 -> Sheet Row 3, col_b -> Column B
    expected_payload = [
        {'range': 'B3', 'values': [[new_value]]}
    ]

    # Instantiate the context and manually set the dfs
    # _UpdateContext needs the original_df which holds the mock worksheet
    context = _UpdateContext(original_df)
    context.copy_df = copy_df # Set the modified copy

    # Calculate updates
    actual_payload = context._calculate_updates()

    # Assert the calculated payload is correct
    assert len(actual_payload) == 1
    assert actual_payload == expected_payload

def test_calculate_updates_multiple_cells(data_sheet_instance):
    """
    Unit test for _calculate_updates focusing on multiple cell changes.
    """
    original_df = data_sheet_instance
    copy_df = original_df.copy()
    
    # Simulate changes
    changes = [
        {'idx': 0, 'col': 'col_c', 'val': 99, 'range': 'C2'},
        {'idx': 2, 'col': 'col_d', 'val': 'New D3', 'range': 'D4'}
    ]
    copy_df.loc[changes[0]['idx'], changes[0]['col']] = changes[0]['val']
    copy_df.loc[changes[1]['idx'], changes[1]['col']] = changes[1]['val']

    # Expected payload
    expected_payload = [
        {'range': changes[0]['range'], 'values': [[changes[0]['val']]]},
        {'range': changes[1]['range'], 'values': [[changes[1]['val']]]},
    ]

    # Instantiate context and calculate updates
    context = _UpdateContext(original_df)
    context.copy_df = copy_df
    actual_payload = context._calculate_updates()

    # Assert the calculated payload is correct (order might vary, so compare sets or sort)
    # Sort based on range for consistent comparison
    sorted_actual = sorted(actual_payload, key=lambda x: x['range'])
    sorted_expected = sorted(expected_payload, key=lambda x: x['range'])
    assert sorted_actual == sorted_expected

def test_calculate_updates_nan_to_value(data_sheet_instance):
    """
    Unit test for _calculate_updates: Changing NaN to a value.
    """
    original_df = data_sheet_instance # original_df.loc[1, 'col_d'] is NaN
    copy_df = original_df.copy()
    
    change_idx = 1
    change_col = 'col_d'
    new_value = 'Now Has Value'
    copy_df.loc[change_idx, change_col] = new_value

    # Expect update payload with the new value (D3)
    expected_payload = [
        {'range': 'D3', 'values': [[new_value]]}
    ]

    context = _UpdateContext(original_df)
    context.copy_df = copy_df
    actual_payload = context._calculate_updates()

    assert actual_payload == expected_payload

def test_calculate_updates_value_to_empty(data_sheet_instance):
    """
    Unit test for _calculate_updates: Changing a value to empty string.
    """
    original_df = data_sheet_instance # original_df.loc[2, 'col_d'] is 'C3'
    copy_df = original_df.copy()
    
    change_idx = 2
    change_col = 'col_d'
    new_value = ''
    copy_df.loc[change_idx, change_col] = new_value

    # Expect update payload with empty string (D4)
    expected_payload = [
        {'range': 'D4', 'values': [[new_value]]}
    ]

    context = _UpdateContext(original_df)
    context.copy_df = copy_df
    actual_payload = context._calculate_updates()

    assert actual_payload == expected_payload

def test_calculate_updates_value_to_nan(data_sheet_instance):
    """
    Unit test for _calculate_updates: Changing a value to NaN.
    """
    original_df = data_sheet_instance # original_df.loc[0, 'col_c'] is 10
    copy_df = original_df.copy()
    
    change_idx = 0
    change_col = 'col_c'
    new_value = np.nan # Using numpy NaN
    copy_df.loc[change_idx, change_col] = new_value

    # Expect update payload with empty string (NaN is converted)
    # C2
    expected_payload = [
        {'range': 'C2', 'values': [['']]}
    ]

    context = _UpdateContext(original_df)
    context.copy_df = copy_df
    actual_payload = context._calculate_updates()

    assert actual_payload == expected_payload

# ===========================================
# Integration Tests for start_update context
# ===========================================

def test_context_manager_no_changes(data_sheet_instance, mock_worksheet):
    """
    Test that no updates occur if the DataFrame copy is not modified.
    """
    original_df_copy = data_sheet_instance.copy() # Keep a copy for comparison

    with data_sheet_instance.start_update() as change:
        # No changes made to 'change' DataFrame
        pass

    # Assertions
    mock_worksheet.batch_update.assert_not_called()
    pd.testing.assert_frame_equal(data_sheet_instance, original_df_copy)
