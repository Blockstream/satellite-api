module Sinatra
  module RegionHelpers
    def region_not_found_error(region)
      halt 404, error_object("region not found", "region #{region} not found", ERROR::CODES[:REGION_NOT_FOUND])
    end
  end
  helpers RegionHelpers
end
