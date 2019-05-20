class AddHasReceiverToRegions < ActiveRecord::Migration[5.2]
  def change
    add_column :regions, :has_receiver, :boolean, default: false
  end
end
