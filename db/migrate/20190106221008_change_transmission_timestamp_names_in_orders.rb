class ChangeTransmissionTimestampNamesInOrders < ActiveRecord::Migration[5.2]
  def change
    rename_column :orders, :upload_started_at, :started_transmission_at
    rename_column :orders, :upload_ended_at, :ended_transmission_at
  end
end
