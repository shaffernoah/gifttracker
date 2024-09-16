import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date
from database import create_tables, add_gift, get_all_gifts, get_gift_categories, get_filtered_gifts, send_thank_you_note, get_gift_suggestions, clear_all_gifts, update_suggestion_feedback
from data_processing import process_gift_data
from utils import format_currency

# Initialize the database
create_tables()

st.set_page_config(page_title="Gift Tracker", layout="wide")

# Sidebar navigation
page = st.sidebar.radio("Navigation", ["Gift Tracker", "Gift Suggestions"])

if page == "Gift Tracker":
    st.title("Gift Tracker")

    # Input form for gift information
    with st.form("gift_form"):
        st.subheader("Add a New Gift")
        giver = st.text_input("Giver Name")
        gift_details = st.text_area("Gift Details")
        date_received = st.date_input("Date Received", value=datetime.now())
        cost = st.number_input("Cost (optional)", min_value=0.0, step=0.01)
        category = st.text_input("Category (optional)")
        
        submitted = st.form_submit_button("Add Gift")
        if submitted:
            if giver and gift_details and date_received:
                add_gift(giver, gift_details, date_received, cost, category)
                st.success("Gift added successfully!")
            else:
                st.error("Please fill in all required fields.")

    # Filtering options
    st.sidebar.header("Filter Gifts")
    categories = get_gift_categories()
    selected_category = st.sidebar.selectbox("Select Category", ["All"] + categories)
    start_date = st.sidebar.date_input("Start Date", value=None)
    end_date = st.sidebar.date_input("End Date", value=None)

    # Apply filters button
    apply_filters = st.sidebar.button("Apply Filters")

    # Clear all gifts button
    if st.sidebar.button("Clear All Gifts"):
        clear_all_gifts()
        st.sidebar.success("All gift data has been cleared!")
        st.rerun()

    # Fetch and process gift data
    if apply_filters:
        gifts_df = get_filtered_gifts(
            category=selected_category if selected_category != "All" else None,
            start_date=start_date,
            end_date=end_date
        )
    else:
        gifts_df = get_all_gifts()

    if gifts_df:
        # Update the DataFrame creation to include all 7 columns
        df = pd.DataFrame(gifts_df, columns=['id', 'giver', 'gift_details', 'date_received', 'cost', 'category', 'thank_you_sent'])
        
        total_gifts, total_givers, total_value, gifts_by_date = process_gift_data(df)

        # Display summary statistics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Gifts Received", total_gifts)
        col2.metric("Total Gift Givers", total_givers)
        col3.metric("Total Value of Gifts", format_currency(total_value))

        # Display gift list
        st.subheader("Gift List")
        df['date_received'] = pd.to_datetime(df['date_received']).dt.date
        df['cost'] = df['cost'].apply(format_currency)
        df['thank_you_sent'] = df['thank_you_sent'].map({True: 'Yes', False: 'No'})
        st.dataframe(df)

        # Thank you note form
        st.subheader("Send Thank You Note")
        with st.form("thank_you_form"):
            gift_id = st.selectbox("Select Gift", df['id'].tolist(), format_func=lambda x: f"Gift from {df[df['id'] == x]['giver'].values[0]} - {df[df['id'] == x]['gift_details'].values[0]}")
            note = st.text_area("Thank You Note")
            send_note = st.form_submit_button("Send Thank You Note")
            
            if send_note:
                if note:
                    if send_thank_you_note(gift_id, note):
                        st.success("Thank you note sent successfully!")
                    else:
                        st.error("Failed to send thank you note. Please try again.")
                else:
                    st.error("Please write a thank you note before sending.")

        # Calendar view
        st.subheader("Gift Calendar")
        if isinstance(gifts_by_date, pd.Series) and not gifts_by_date.empty:
            # Get the current month and year
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year

            # Filter gifts for the current month
            current_month_gifts = gifts_by_date[gifts_by_date.index.month == current_month]

            # Create calendar data
            calendar_data = pd.DataFrame({
                'date': pd.date_range(start=f"{current_year}-{current_month:02d}-01", 
                                      end=f"{current_year}-{current_month:02d}-{pd.Timestamp(current_year, current_month, 1).days_in_month}", 
                                      freq='D'),
                'gifts': 0
            }).set_index('date')

            calendar_data.loc[current_month_gifts.index, 'gifts'] = current_month_gifts.values

            # Create the calendar figure using a heatmap
            fig = go.Figure(data=go.Heatmap(
                z=calendar_data['gifts'],
                x=calendar_data.index.day,
                y=calendar_data.index.strftime('%A'),
                colorscale='YlOrRd'
            ))

            fig.update_layout(
                title=f"Gifts Received in {current_date.strftime('%B %Y')}",
                height=400,
                xaxis_title="Day of Month",
                yaxis_title="Day of Week"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No gifts recorded for the current month.")
    else:
        st.info("No gifts found with the current filters.")

elif page == "Gift Suggestions":
    st.title("Gift Suggestions")

    # Gift Suggestion Feature
    suggestion_giver = st.selectbox("Select Giver for Suggestions", ["All"] + list(set([gift[1] for gift in get_all_gifts()])))
    suggestion_category = st.selectbox("Select Category for Suggestions", ["All"] + get_gift_categories())

    if st.button("Get Gift Suggestions"):
        st.info("Mark this suggestion as helpful for future recommendations.")
        
        result = get_gift_suggestions(
            giver=suggestion_giver if suggestion_giver != "All" else None,
            category=suggestion_category if suggestion_category != "All" else None,
            num_suggestions=1
        )
        
        if result["status"] == "success":
            st.write("Here's a gift suggestion based on past gifts:")
            suggestion = result["suggestions"][0]
            st.write(f"{suggestion['category']}: {suggestion['gift']}")
            st.write(f"Estimated Cost: {format_currency(suggestion['cost'])}")
            col1, col2 = st.columns(2)
            if col1.button("Helpful", key=f"helpful_{suggestion['id']}"):
                if update_suggestion_feedback(suggestion['id'], True):
                    st.success("Suggestion marked as helpful!")
                else:
                    st.error("Failed to update suggestion feedback.")
            if col2.button("Not Helpful", key=f"not_helpful_{suggestion['id']}"):
                if update_suggestion_feedback(suggestion['id'], False):
                    st.success("Suggestion marked as not helpful!")
                else:
                    st.error("Failed to update suggestion feedback.")
            
            if st.button("Show More Suggestions"):
                more_suggestions = get_gift_suggestions(
                    giver=suggestion_giver if suggestion_giver != "All" else None,
                    category=suggestion_category if suggestion_category != "All" else None,
                    num_suggestions=3
                )
                st.write(f"Debug: more_suggestions = {more_suggestions}")  # Debug print
                if more_suggestions["status"] == "success" and len(more_suggestions["suggestions"]) > 1:
                    st.write("Additional gift suggestions:")
                    for index, suggestion in enumerate(more_suggestions["suggestions"][1:], start=1):
                        st.write(f"{suggestion['category']}: {suggestion['gift']}")
                        st.write(f"Estimated Cost: {format_currency(suggestion['cost'])}")
                        col1, col2 = st.columns(2)
                        if col1.button("Helpful", key=f"helpful_{suggestion['id']}_{index}"):
                            if update_suggestion_feedback(suggestion['id'], True):
                                st.success("Suggestion marked as helpful!")
                            else:
                                st.error("Failed to update suggestion feedback.")
                        if col2.button("Not Helpful", key=f"not_helpful_{suggestion['id']}_{index}"):
                            if update_suggestion_feedback(suggestion['id'], False):
                                st.success("Suggestion marked as not helpful!")
                            else:
                                st.error("Failed to update suggestion feedback.")
                        st.write("---")
                else:
                    st.warning("No additional suggestions available.")
        elif result["status"] == "no_suggestions":
            st.warning(result["message"])
            st.info("Try selecting different criteria or add more gifts to get suggestions.")
        else:
            st.error(result["message"])